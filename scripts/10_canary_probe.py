"""Direct canary extraction probe (Carlini-style): given everything up to the secret,
does the model emit it?

    # vLLM server running with the k-checkpoint served as <model>-k<k>:
    python scripts/10_canary_probe.py --model gemma-2-9b --k 5

Prompts the model with each canary host file's exact training text truncated right
before the secret value, then checks exact / Levenshtein<=2 recovery. This is a
stronger test than the canary task (which only gives the signature): if this is also
zero, the model genuinely did not memorise the canaries.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
import Levenshtein
from dotenv import load_dotenv

from exposure_gap.config import DecodeSpec, Settings
from exposure_gap.corpus import CanaryInjector, CorpusStore
from exposure_gap.eval.infer import BackendFactory, GenerationRequest
from exposure_gap.phases import Phases
from exposure_gap.utils import setup_logging


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", required=True)
@click.option("--k", "k", default=5)
@click.option("--backend", default="vllm")
@click.option("--context-chars", default=400, help="chars of file context before the secret")
def main(root: str, model_id: str, k: int, backend: str, context_chars: int) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()
    s = Settings.load(root)
    store = CorpusStore(s.corpus_dir)
    canaries = Phases(s).load_canaries()
    injector = CanaryInjector()

    be = BackendFactory().create(model_id, k, backend)
    decode = DecodeSpec(temperature=0.0, n_samples=1, max_tokens=96)

    exact = near = total = 0
    for fid, canary in canaries.items():
        if not store.has_source(fid):
            continue
        injected = injector.inject(store.read_source(fid), canary)
        idx = injected.find(canary.value)
        if idx < 0:
            continue
        prompt = injected[max(0, idx - context_chars):idx]
        out = be.generate(GenerationRequest(prompt=prompt, decode=decode))[0]
        total += 1
        if canary.value[:60] in out:
            exact += 1
        elif any(Levenshtein.distance(out[i:i + len(canary.value)], canary.value) <= 2
                 for i in range(max(1, len(out) - len(canary.value)))):
            near += 1

    click.echo(f"model={model_id} k={k}: {total} canaries probed | "
               f"exact {exact} ({exact/max(total,1):.1%}) | near {near}")


if __name__ == "__main__":
    main()
