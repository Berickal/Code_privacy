"""``exposure-gap`` command line — one sub-command per report phase (Section 13)."""

from __future__ import annotations

import sys

import click

from .config import Settings
from .phases import Phases
from .utils import setup_logging


@click.group()
@click.option("--root", default=".", help="project root (holds configs/, corpus/, prompts/)")
@click.option("--log-level", default="INFO")
@click.pass_context
def main(ctx: click.Context, root: str, log_level: str) -> None:
    setup_logging(log_level)
    ctx.obj = Phases(Settings.load(root))


@main.command("build-corpus")
@click.option("--stack-v2-bloom", default=None, help="path to the Stack v2 bloom filter")
@click.option("--use-github-time/--no-github-time", default=True)
@click.pass_obj
def build_corpus(phases: Phases, stack_v2_bloom: str | None, use_github_time: bool) -> None:
    """Phase A: verify, deduplicate, match, freeze the split."""
    membership = None
    if stack_v2_bloom:
        from .oracle import StackV2BloomOracle

        membership = StackV2BloomOracle(stack_v2_bloom)
    timestamp = None
    if use_github_time:
        from .oracle import GitHubTimestampOracle

        timestamp = GitHubTimestampOracle()
    report = phases.build_corpus(membership_oracle=membership, timestamp_oracle=timestamp)
    click.echo(report)
    if not report.gate1_pass:
        click.echo("Gate 1 FAILED", err=True)
        sys.exit(1)


@main.command("build-canaries")
@click.pass_obj
def build_canaries(phases: Phases) -> None:
    """Phase B: assign + write the canary registry."""
    canaries = phases.build_canaries()
    click.echo(f"{len(canaries)} canaries written")


@main.command("materialize-prompts")
@click.pass_obj
def materialize_prompts(phases: Phases) -> None:
    """Phase D: write the 30 prompt templates."""
    click.echo(f"{phases.materialize_prompts()} templates written")


@main.command("check-prompts")
@click.pass_obj
def check_prompts(phases: Phases) -> None:
    leakage = phases.check_prompts()
    reg = phases.ctx.prompt_registry
    click.echo(f"prompt version hash: {reg.version_hash}")
    if leakage:
        for line in leakage:
            click.echo(f"LEAKAGE: {line}", err=True)
        sys.exit(1)
    click.echo(f"{len(reg.templates)} templates OK, no target leakage")


@main.command("freeze")
@click.pass_obj
def freeze(phases: Phases) -> None:
    """Phases B-E: write FREEZE.lock."""
    path = phases.write_freeze()
    click.echo(f"wrote {path}")


@main.command("verify-freeze")
@click.pass_obj
def verify_freeze(phases: Phases) -> None:
    violations = phases.verify_freeze()
    if violations:
        for v in violations:
            click.echo(f"VIOLATION: {v}", err=True)
        sys.exit(1)
    click.echo("FREEZE.lock OK")


@main.command("evaluate")
@click.option("--offline", is_flag=True, help="use the echo backend (no network/GPU)")
@click.option("--backend", default=None, help="override model backend (local | vllm | openrouter)")
@click.option("--model", "model_ids", multiple=True, help="restrict to these model id(s)")
@click.option("--quantization", default=None, help="local/vllm quant: bitsandbytes | int8")
@click.option("--batch-size", default=8, help="local backend generation batch size")
@click.option("--task", "tasks", multiple=True)
@click.option("--strategy", "strategies", multiple=True)
@click.option("--k", "k_levels", multiple=True, type=int)
@click.pass_obj
def evaluate(phases: Phases, offline, backend, model_ids, quantization, batch_size, tasks, strategies, k_levels) -> None:
    """Phase F/G: run the (model x k x task x prompt) matrix."""
    models = None
    if backend or model_ids:
        specs = phases.settings.finetune.models
        chosen = [m for m in specs if not model_ids or m.id in model_ids]
        models = [(m.id, backend or m.backend) for m in chosen]
        for mid in model_ids:  # allow ids not in the config
            if not any(m.id == mid for m in specs):
                models.append((mid, backend or "local"))
        models = models or [("echo-model", backend or "echo")]
    df = phases.evaluate(
        models=models,
        offline=offline,
        quantization=quantization,
        batch_size=batch_size,
        tasks=tuple(tasks) or None,
        strategies=tuple(strategies) or None,
        k_levels=tuple(k_levels) or (0, 1, 5, 25),
    )
    click.echo(f"{len(df)} prediction rows")


@main.command("analyse")
@click.option("--predictions", default=None)
@click.option("--model", "model_filter", default=None, help="restrict to one model id")
@click.pass_obj
def analyse(phases: Phases, predictions: str | None, model_filter: str | None) -> None:
    """Phase G: gaps, FDR, interaction, convergence, dose-response, figures."""
    import pandas as pd

    preds = pd.read_parquet(predictions) if predictions else None
    if preds is None:
        p = phases.settings.results_dir / "raw_predictions" / "all_predictions.parquet"
        preds = pd.read_parquet(p)
    if model_filter:
        preds = preds[preds["model"] == model_filter]
    artifacts = phases.analyse(preds)

    g = artifacts.gaps
    cols = ["task", "metric", "model", "k", "prompt", "delta", "ci_low", "ci_high", "p_adj"]
    click.echo("--- exposed-unexposed gap Δ_π (all cells, sorted by |Δ|) ---")
    click.echo(
        g.reindex(g["delta"].abs().sort_values(ascending=False).index)
        .head(25)[cols].to_string(index=False)
    )
    n_sig = int(g["significant"].sum()) if "significant" in g else 0
    click.echo(f"\nFDR-significant (q<0.05): {n_sig} / {len(g)}")


if __name__ == "__main__":
    main()
