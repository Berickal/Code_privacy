#!/usr/bin/env bash
# Fine-tune -> run the goal probes on the base model and every checkpoint (transformers) -> score -> report.
#
#   ./run_pipeline.sh                    # all stages
#   ./run_pipeline.sh finetune infer     # only some stages (finetune | infer | eval | report)
#
# Configuration through environment variables, e.g.
#   MODEL=Qwen/Qwen2.5-Coder-7B-Instruct EPOCHS="1 3 5 10" RUN=qwen7b_full ./run_pipeline.sh
#   LIMIT=20 EPOCHS="1 2" ./run_pipeline.sh          # smoke test: 20 probes per goal
#
# Every stage is idempotent: existing checkpoints are kept, inference resumes where it stopped,
# so the same command can be re-run after a crash.
#
# GPUs (detected from CUDA_VISIBLE_DEVICES or nvidia-smi):
#   training  : NUM_GPUS > 1 -> torchrun, one process per GPU (FSDP for full fine-tuning, DDP for LoRA)
#   inference : NUM_GPUS / GPUS_PER_MODEL workers in parallel, each with GPUS_PER_MODEL GPUs and a share
#               of the probes, e.g. NUM_GPUS=8 GPUS_PER_MODEL=2 -> 4 copies of a 32B model
set -euo pipefail
cd "$(dirname "$0")"

MODEL=${MODEL:-meta-llama/Llama-3.2-3B-Instruct}
METHOD=${METHOD:-full}                       # lora | full
EPOCHS=${EPOCHS-"1 3 5"}                     # EPOCHS="" = base model only (inference)
RUN=${RUN:-$(basename "$MODEL")_${METHOD}}
RUN_DIR=${RUN_DIR:-runs/$RUN}
PYTHON=${PYTHON:-python}
FT_ARGS=${FT_ARGS:-}                         # extra finetune.py args, e.g. "--loss-on-prompt --lr 2e-4"
LORA_R=${LORA_R:-16}
BATCH_SIZE=${BATCH_SIZE:-16}                 # max probes per generate() call
MAX_BATCH_TOKENS=${MAX_BATCH_TOKENS:-65536}  # (longest prompt + new tokens) x batch size; lower it on small GPUs
LIMIT=${LIMIT:-}                             # probes per goal (empty = all)
INFER_ARGS=${INFER_ARGS:-}                   # extra llm_inference.py args, e.g. "--goals secret_extraction --n 5 --temperature 0.8"
GPUS_PER_MODEL=${GPUS_PER_MODEL:-1}          # inference: GPUs holding one copy of the model (2 for 27-32B on 80 GB)

detect_gpus() {
    if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then echo "$CUDA_VISIBLE_DEVICES" | tr ',' ' '
    elif command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=index --format=csv,noheader | tr '\n' ' '
    fi
}
read -r -a ALL_GPUS <<< "$(detect_gpus)"
NUM_GPUS=${NUM_GPUS:-${#ALL_GPUS[@]}}        # GPUs to use (default: all visible; 0 = CPU / Apple MPS)
[ "$NUM_GPUS" -le "${#ALL_GPUS[@]}" ] || { echo "NUM_GPUS=$NUM_GPUS but only ${#ALL_GPUS[@]} GPU(s) visible" >&2; exit 1; }
GPUS=(${ALL_GPUS[@]+"${ALL_GPUS[@]:0:$NUM_GPUS}"})
WORKERS=$(( NUM_GPUS >= GPUS_PER_MODEL && GPUS_PER_MODEL > 0 ? NUM_GPUS / GPUS_PER_MODEL : 1 ))
join_gpus() { local IFS=,; echo "$*"; }      # join_gpus 0 1 2 -> "0,1,2"

STAGES=("$@")
[ ${#STAGES[@]} -eq 0 ] && STAGES=(finetune infer eval report)
CKPT_DIR=$RUN_DIR/checkpoints
LOG_DIR=$RUN_DIR/logs
mkdir -p "$LOG_DIR" "$RUN_DIR/generations" "$RUN_DIR/scores"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_DIR/pipeline.log"; }
has_stage() { [[ " ${STAGES[*]} " == *" $1 "* ]]; }
checkpoints() { for e in $EPOCHS; do echo "epoch_$e"; done; }

cat > "$RUN_DIR/pipeline_config.env" <<EOF
MODEL=$MODEL
METHOD=$METHOD
EPOCHS="$EPOCHS"
FT_ARGS="$FT_ARGS"
LORA_R=$LORA_R
LIMIT=$LIMIT
INFER_ARGS="$INFER_ARGS"
NUM_GPUS=$NUM_GPUS
GPUS_PER_MODEL=$GPUS_PER_MODEL
EOF

# ---------------------------------------------------------------------------- finetune
if has_stage finetune; then
    [ -n "$EPOCHS" ] || { log "EPOCHS is empty: nothing to fine-tune"; exit 1; }
    if [ "$NUM_GPUS" -gt 1 ]; then
        launch=(env CUDA_VISIBLE_DEVICES="$(join_gpus "${GPUS[@]}")" $PYTHON -m torch.distributed.run
                --standalone --nproc_per_node "$NUM_GPUS")
    elif [ "$NUM_GPUS" -eq 1 ]; then
        launch=(env CUDA_VISIBLE_DEVICES="${GPUS[0]}" $PYTHON)   # 1 GPU: no DataParallel replication
    else
        launch=($PYTHON)
    fi
    log "finetune $MODEL ($METHOD) epochs: $EPOCHS on $NUM_GPUS GPU(s)"
    # shellcheck disable=SC2086
    "${launch[@]}" finetune.py --model "$MODEL" --method "$METHOD" --out "$CKPT_DIR" --epochs $EPOCHS \
        --lora-r "$LORA_R" $FT_ARGS 2>&1 | tee -a "$LOG_DIR/finetune.log"
fi

# ---------------------------------------------------------------------------- infer
infer() {   # infer <model or checkpoint> <extra llm_inference.py args...>
    local model=$1; shift
    local common=(--model "$model" --out-dir "$RUN_DIR/generations" --batch-size "$BATCH_SIZE"
                  --max-batch-tokens "$MAX_BATCH_TOKENS")
    [ -n "$LIMIT" ] && common+=(--limit "$LIMIT")
    if [ "$WORKERS" -le 1 ]; then
        log "inference: $model $* on GPU(s) [${GPUS[*]+${GPUS[*]}}]"
        local env_gpus=()
        [ "$NUM_GPUS" -gt 0 ] && env_gpus=(env CUDA_VISIBLE_DEVICES="$(join_gpus "${GPUS[@]}")")
        # shellcheck disable=SC2086
        ${env_gpus[@]+"${env_gpus[@]}"} $PYTHON llm_inference.py "${common[@]}" "$@" $INFER_ARGS \
            2>&1 | tee -a "$LOG_DIR/inference.log"
        return
    fi
    # data parallel: one worker per group of GPUS_PER_MODEL GPUs, each on its own share of the probes
    local pids=() i group failed=0
    for (( i = 0; i < WORKERS; i++ )); do
        group=$(join_gpus "${GPUS[@]:$(( i * GPUS_PER_MODEL )):$GPUS_PER_MODEL}")
        log "inference worker $i/$WORKERS on GPU(s) $group: $model $*"
        # shellcheck disable=SC2086
        CUDA_VISIBLE_DEVICES=$group $PYTHON llm_inference.py "${common[@]}" "$@" $INFER_ARGS \
            --num-shards "$WORKERS" --shard-id "$i" > "$LOG_DIR/inference_worker$i.log" 2>&1 &
        pids+=($!)
    done
    for (( i = 0; i < WORKERS; i++ )); do
        wait "${pids[$i]}" || { failed=1; log "worker $i failed — see $LOG_DIR/inference_worker$i.log"; }
    done
    cat "$LOG_DIR"/inference_worker*.log >> "$LOG_DIR/inference.log"
    $PYTHON llm_inference.py "${common[@]}" "$@" --merge 2>&1 | tee -a "$LOG_DIR/inference.log"
    [ "$failed" -eq 0 ] || { log "inference failed for $model (re-run to resume)"; exit 1; }
}

if has_stage infer; then
    if [ "$METHOD" = lora ]; then
        # the base model is loaded once; every epoch adapter is applied in turn
        adapters=()
        for c in $(checkpoints); do
            [ -f "$CKPT_DIR/$c/adapter_config.json" ] || { log "missing adapter $CKPT_DIR/$c"; exit 1; }
            adapters+=("$c=$CKPT_DIR/$c")
        done
        infer "$MODEL" --name base ${adapters[@]+--adapters "${adapters[@]}"}
    else
        # full fine-tuning: one model load per checkpoint (checked first, so a missing one fails fast)
        for c in $(checkpoints); do
            [ -f "$CKPT_DIR/$c/config.json" ] || { log "missing checkpoint $CKPT_DIR/$c"; exit 1; }
        done
        infer "$MODEL" --name base
        for c in $(checkpoints); do infer "$CKPT_DIR/$c" --name "$c"; done
    fi
fi

# ---------------------------------------------------------------------------- eval
if has_stage eval; then
    for name in base $(checkpoints); do
        gen=$RUN_DIR/generations/$name.jsonl
        [ -f "$gen" ] || { log "no generations for $name, skipping"; continue; }
        log "evaluate: $name"
        $PYTHON evaluate.py --generations "$gen" --out "$RUN_DIR/scores/$name.jsonl" \
            2>&1 | tee -a "$LOG_DIR/evaluate.log"
    done
fi

# ---------------------------------------------------------------------------- report
if has_stage report; then
    log "report"
    $PYTHON report.py --run-dir "$RUN_DIR" 2>&1 | tee -a "$LOG_DIR/report.log"
    log "done: $RUN_DIR/report/report.md"
fi
