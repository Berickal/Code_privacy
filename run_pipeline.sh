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
set -euo pipefail
cd "$(dirname "$0")"

MODEL=${MODEL:-meta-llama/Llama-3.2-3B-Instruct}
METHOD=${METHOD:-full}                       # lora | full
EPOCHS=${EPOCHS:-"1 3 5"}
RUN=${RUN:-$(basename "$MODEL")_${METHOD}}
RUN_DIR=${RUN_DIR:-runs/$RUN}
PYTHON=${PYTHON:-python}
FT_ARGS=${FT_ARGS:-}                         # extra finetune.py args, e.g. "--loss-on-prompt --lr 2e-4"
LORA_R=${LORA_R:-16}
BATCH_SIZE=${BATCH_SIZE:-16}                 # max probes per generate() call
MAX_BATCH_TOKENS=${MAX_BATCH_TOKENS:-65536}  # (longest prompt + new tokens) x batch size; lower it on small GPUs
LIMIT=${LIMIT:-}                             # probes per goal (empty = all)
INFER_ARGS=${INFER_ARGS:-}                   # extra llm_inference.py args, e.g. "--goals secret_extraction --n 5 --temperature 0.8"

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
EOF

# ---------------------------------------------------------------------------- finetune
if has_stage finetune; then
    log "finetune $MODEL ($METHOD) epochs: $EPOCHS"
    # shellcheck disable=SC2086
    $PYTHON finetune.py --model "$MODEL" --method "$METHOD" --out "$CKPT_DIR" --epochs $EPOCHS \
        --lora-r "$LORA_R" $FT_ARGS 2>&1 | tee -a "$LOG_DIR/finetune.log"
fi

# ---------------------------------------------------------------------------- infer
infer() {   # infer <model or checkpoint> <extra llm_inference.py args...>
    local model=$1; shift
    local limit_arg=()
    [ -n "$LIMIT" ] && limit_arg=(--limit "$LIMIT")
    log "inference: $model $*"
    # shellcheck disable=SC2086
    $PYTHON llm_inference.py --model "$model" --out-dir "$RUN_DIR/generations" \
        --batch-size "$BATCH_SIZE" --max-batch-tokens "$MAX_BATCH_TOKENS" \
        ${limit_arg[@]+"${limit_arg[@]}"} "$@" $INFER_ARGS 2>&1 | tee -a "$LOG_DIR/inference.log"
}

if has_stage infer; then
    if [ "$METHOD" = lora ]; then
        # the base model is loaded once; every epoch adapter is applied in turn
        adapters=()
        for c in $(checkpoints); do
            [ -f "$CKPT_DIR/$c/adapter_config.json" ] || { log "missing adapter $CKPT_DIR/$c"; exit 1; }
            adapters+=("$c=$CKPT_DIR/$c")
        done
        infer "$MODEL" --name base --adapters "${adapters[@]}"
    else
        # full fine-tuning: one model load per checkpoint
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
