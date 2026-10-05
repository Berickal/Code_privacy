"""Aggregate the scores of every checkpoint of a run (base, epoch_1, epoch_3, ...).

    python report.py --run-dir runs/llama3b_lora

Reads   <run-dir>/scores/<checkpoint>.jsonl   (written by evaluate.py)
Writes  <run-dir>/report/summary.csv  mean + 95 % CI per (goal, metric, checkpoint, source, split, strategy)
        <run-dir>/report/gaps.csv     SWH: leak - unleak, and its change vs the base model (diff-in-diff)
                                      CodeParrot: checkpoint - base (paired on the same probes)
        <run-dir>/report/report.md    headline tables
        <run-dir>/report/*.png        metric vs epoch per goal, goal-1 information ladder

CIs are cluster bootstraps over files (a file contributes several probes / items).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
from leak_utils import GOAL_LICENSE, GOAL_REPRODUCTION, GOAL_SECRETS, normalise_goal  # noqa: E402

HEADLINE = {  # goal -> metrics reported (the first one is the primary metric in report.md / plots)
    GOAL_REPRODUCTION: ["char_sim", "ident_recall_new", "line_run", "ast_seq_sim", "exact"],
    GOAL_SECRETS: ["exact", "near", "lcs_frac", "format_ok"],
    GOAL_LICENSE: ["repo_correct", "file_correct", "repo_family_correct", "file_family_correct",
              "header_char_sim", "header_holder_recall"],
}
B = 1000


def epoch_of(ckpt: str) -> int:
    m = re.search(r"(\d+)$", ckpt)
    return int(m.group(1)) if m and ckpt != "base" else 0


def load(run_dir: Path) -> pd.DataFrame:
    frames = []
    for f in sorted((run_dir / "scores").glob("*.jsonl")):
        d = pd.read_json(f, lines=True)
        d["checkpoint"] = f.stem
        frames.append(d)
    if not frames:
        raise SystemExit(f"no scores in {run_dir / 'scores'}")
    df = pd.concat(frames, ignore_index=True)
    df["goal"] = df.goal.map(normalise_goal)          # scores written with the legacy labels
    df["epoch"] = df.checkpoint.map(epoch_of)
    df["population"] = df.source.map({"code_parrot": "CP"}).fillna("SWH") + "-" + df.split
    return df


def file_means(d: pd.DataFrame, metric: str) -> np.ndarray:
    return d.dropna(subset=[metric]).groupby("file_id")[metric].mean().astype(float).to_numpy()


def boot_mean(x: np.ndarray, rng) -> tuple[float, float, float]:
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    bs = rng.choice(x, size=(B, len(x))).mean(axis=1)
    return (x.mean(), *np.percentile(bs, [2.5, 97.5]))


def boot_diff(a: np.ndarray, b: np.ndarray, rng) -> tuple[float, float, float]:
    if len(a) == 0 or len(b) == 0:
        return (np.nan, np.nan, np.nan)
    bs = rng.choice(a, size=(B, len(a))).mean(axis=1) - rng.choice(b, size=(B, len(b))).mean(axis=1)
    return (a.mean() - b.mean(), *np.percentile(bs, [2.5, 97.5]))


def summary(df: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    for (goal, ckpt, pop, strategy), d in df.groupby(["goal", "checkpoint", "population", "strategy"]):
        for metric in HEADLINE[goal]:
            if metric not in d or d[metric].isna().all():
                continue
            x = file_means(d, metric)
            m, lo, hi = boot_mean(x, rng)
            rows.append({"goal": goal, "metric": metric, "checkpoint": ckpt, "epoch": epoch_of(ckpt),
                         "population": pop, "strategy": strategy, "n_files": len(x),
                         "mean": m, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)


def gaps(df: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    base = df[df.checkpoint == "base"]
    for (goal, ckpt, strategy), d in df.groupby(["goal", "checkpoint", "strategy"]):
        b = base[(base.goal == goal) & (base.strategy == strategy)]
        for metric in HEADLINE[goal]:
            if metric not in d or d[metric].isna().all():
                continue
            # SWH: exposure gap, and its change relative to the base model
            leak, unleak = (file_means(d[d.population == f"SWH-{s}"], metric) for s in ("leak", "unleak"))
            g, lo, hi = boot_diff(leak, unleak, rng)
            row = {"goal": goal, "metric": metric, "checkpoint": ckpt, "epoch": epoch_of(ckpt), "strategy": strategy,
                   "swh_gap": g, "swh_gap_low": lo, "swh_gap_high": hi}
            if ckpt != "base" and len(b):
                bl, bu = (file_means(b[b.population == f"SWH-{s}"], metric) for s in ("leak", "unleak"))
                if len(bl) and len(bu) and len(leak) and len(unleak):
                    did = [(rng.choice(leak, len(leak)).mean() - rng.choice(unleak, len(unleak)).mean())
                           - (rng.choice(bl, len(bl)).mean() - rng.choice(bu, len(bu)).mean()) for _ in range(B)]
                    row.update(swh_did=(leak.mean() - unleak.mean()) - (bl.mean() - bu.mean()),
                               swh_did_low=np.percentile(did, 2.5), swh_did_high=np.percentile(did, 97.5))
                # CodeParrot: fine-tuned - base, paired on probe ids, clustered by file
                cp = d[d.population == "CP-leak"][["id", "file_id", metric]].merge(
                    b[b.population == "CP-leak"][["id", metric]], on="id", suffixes=("", "_base")).dropna()
                if len(cp):
                    cp["delta"] = cp[metric].astype(float) - cp[f"{metric}_base"].astype(float)
                    m, lo, hi = boot_mean(cp.groupby("file_id").delta.mean().to_numpy(), rng)
                    row.update(cp_delta=m, cp_delta_low=lo, cp_delta_high=hi)
            rows.append(row)
    return pd.DataFrame(rows)


def fmt(m, lo, hi) -> str:
    return "—" if pd.isna(m) else f"{m:.3f} [{lo:.3f}, {hi:.3f}]"


def markdown(summ: pd.DataFrame, gp: pd.DataFrame, run_dir: Path) -> str:
    out = [f"# Report — `{run_dir.name}`", ""]
    ckpts = sorted(summ.checkpoint.unique(), key=epoch_of)
    for goal, metrics in HEADLINE.items():
        s = summ[(summ.goal == goal)]
        if s.empty:
            continue
        out.append(f"## {goal}")
        for metric in metrics[:2] if goal != GOAL_LICENSE else ["repo_correct", "file_correct", "header_char_sim"]:
            sm = s[s.metric == metric]
            if sm.empty:
                continue
            out += [f"### `{metric}` — mean [95 % CI] by strategy", ""]
            table = sm.assign(cell=[fmt(*v) for v in sm[["mean", "ci_low", "ci_high"]].to_numpy()]) \
                .pivot_table(index="strategy", columns=["population", "checkpoint"], values="cell", aggfunc="first")
            table = table.reindex(columns=sorted(table.columns, key=lambda c: (c[0], epoch_of(c[1]))))
            table.columns = [f"{pop} · {ck}" for pop, ck in table.columns]
            out += [table.to_markdown(), ""]
            g = gp[(gp.goal == goal) & (gp.metric == metric) & (gp.checkpoint != "base")]
            if not g.empty:
                out += [f"**Gaps** (`{metric}`): SWH leak−unleak, its change vs base (diff-in-diff), "
                        "and CodeParrot fine-tuned−base", ""]
                gt = g.assign(
                    swh_gap=[fmt(*v) for v in g[["swh_gap", "swh_gap_low", "swh_gap_high"]].to_numpy()],
                    swh_did=[fmt(*v) for v in g.reindex(columns=["swh_did", "swh_did_low", "swh_did_high"]).to_numpy()],
                    cp_delta=[fmt(*v) for v in g.reindex(columns=["cp_delta", "cp_delta_low", "cp_delta_high"]).to_numpy()],
                )[["strategy", "checkpoint", "swh_gap", "swh_did", "cp_delta"]].sort_values(
                    ["strategy", "checkpoint"], key=lambda c: c.map(epoch_of) if c.name == "checkpoint" else c)
                out += [gt.to_markdown(index=False), ""]
    out += ["", f"Checkpoints: {', '.join(ckpts)}"]
    return "\n".join(out)


def plots(summ: pd.DataFrame, df: pd.DataFrame, out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: no plots")
        return
    colors = {"CP-leak": "#1f77b4", "SWH-leak": "#d62728", "SWH-unleak": "#7f7f7f"}
    for goal, metrics in HEADLINE.items():
        s = summ[(summ.goal == goal) & (summ.metric == metrics[0])]
        if s.empty or s.epoch.nunique() < 1:
            continue
        strategies = sorted(s.strategy.unique())
        fig, axes = plt.subplots(1, len(strategies), figsize=(3.2 * len(strategies), 3), sharey=True, squeeze=False)
        for ax, strat in zip(axes[0], strategies):
            for pop, d in s[s.strategy == strat].groupby("population"):
                d = d.sort_values("epoch")
                ax.plot(d.epoch, d["mean"], marker="o", label=pop, color=colors.get(pop))
                ax.fill_between(d.epoch, d.ci_low, d.ci_high, alpha=0.15, color=colors.get(pop))
            ax.set_title(strat, fontsize=9)
            ax.set_xlabel("epoch (0 = base)")
        axes[0][0].set_ylabel(metrics[0])
        axes[0][-1].legend(fontsize=8)
        fig.suptitle(f"{goal} — {metrics[0]}")
        fig.tight_layout()
        fig.savefig(out_dir / f"{goal}_{metrics[0]}_by_epoch.png", dpi=150)
        plt.close(fig)

    # goal 1: reproduction vs information given by the prompt, base vs last checkpoint
    g1 = df[(df.goal == GOAL_REPRODUCTION) & df.prompt_identifier_recall.notna()]
    if not g1.empty:
        last = max(g1.checkpoint.unique(), key=epoch_of)
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), sharey=True)
        for ax, ckpt in zip(axes, ["base", last]):
            d = g1[g1.checkpoint == ckpt].copy()
            d["bin"] = pd.cut(d.prompt_identifier_recall, [-0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
            for pop, dd in d.groupby("population"):
                m = dd.groupby("bin", observed=True).char_sim.mean()
                ax.plot([iv.mid for iv in m.index], m.values, marker="o", label=pop, color=colors.get(pop))
            ax.set_title(ckpt)
            ax.set_xlabel("identifiers given by the prompt (fraction)")
        axes[0].set_ylabel("char_sim")
        axes[1].legend(fontsize=8)
        fig.suptitle(f"{GOAL_REPRODUCTION} — reproduction vs information in the prompt")
        fig.tight_layout()
        fig.savefig(out_dir / f"{GOAL_REPRODUCTION}_ladder.png", dpi=150)
        plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    df = load(args.run_dir)
    out_dir = args.run_dir / "report"
    out_dir.mkdir(parents=True, exist_ok=True)
    summ = summary(df, rng)
    gp = gaps(df, rng)
    summ.to_csv(out_dir / "summary.csv", index=False)
    gp.to_csv(out_dir / "gaps.csv", index=False)
    (out_dir / "report.md").write_text(markdown(summ, gp, args.run_dir))
    plots(summ, df, out_dir)
    (out_dir / "counts.json").write_text(json.dumps(
        df.groupby(["checkpoint", "goal", "population"]).size().rename("n").reset_index().to_dict("records"), indent=1))
    print(f"report -> {out_dir}")


if __name__ == "__main__":
    main()
