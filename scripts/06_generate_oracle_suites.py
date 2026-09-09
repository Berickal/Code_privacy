"""Phase B: scaffold an oracle pytest suite per exposed reproduction target.

    python scripts/06_generate_oracle_suites.py                 # scaffold stubs
    python scripts/06_generate_oracle_suites.py --model <slug>  # draft assertions via LLM

Suites are written from the **signature + docstring only** (never the implementation —
report Section 15 test-contamination mitigation) to tests/oracle_suites/<file_id>.py.
Each generated file is marked NEEDS_REVIEW; a human confirms the assertions before the
suite is frozen into FREEZE.lock.

pass@1 is optional: lexical F1, AST edit distance and dataflow similarity all work
without oracle suites, so Phase F can run before this step is complete.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
from dotenv import load_dotenv
from tqdm import tqdm

from exposure_gap import SPLIT_EXPOSED
from exposure_gap.config import Settings
from exposure_gap.corpus import CorpusStore
from exposure_gap.eval.infer import GenerationRequest, OpenRouterBackend
from exposure_gap.config import DecodeSpec
from exposure_gap.prompts import TargetFieldExtractor
from exposure_gap.utils import ensure_dir, get_logger, setup_logging

log = get_logger()

_STUB = '''\
"""Oracle suite for {file_id}  —  NEEDS_REVIEW
Function: {func}
Spec (docstring):
{doc_indented}

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import {func}  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert {func}(...) == ...
    assert callable({func})
'''

_LLM_SYSTEM = (
    "You write pytest test suites for a Python function given ONLY its signature and "
    "docstring. Never assume implementation details beyond the spec. Output only a "
    "Python file that does `from solution import <name>` and defines 3-6 `test_*` "
    "functions with concrete assertions. No prose."
)


def _func_name(signature: str) -> str:
    import re

    m = re.search(r"def\s+(\w+)", signature)
    return m.group(1) if m else "target"


def _scaffold(file_id: str, signature: str, docstring: str) -> str:
    func = _func_name(signature)
    return _STUB.format(
        file_id=file_id,
        func=func,
        doc_indented=textwrap.indent(docstring or "(no docstring)", "    "),
    )


def _llm_draft(backend: OpenRouterBackend, signature: str, docstring: str) -> str | None:
    prompt = (
        f"{_LLM_SYSTEM}\n\nSignature:\n{signature}\n\nDocstring:\n\"\"\"{docstring}\"\"\"\n"
    )
    try:
        out = backend.generate(
            GenerationRequest(prompt=prompt, decode=DecodeSpec(temperature=0.0, n_samples=1, max_tokens=900))
        )[0]
    except Exception as exc:  # pragma: no cover - network
        log.warning("llm draft failed: {}", exc)
        return None
    if "```" in out:
        out = out.split("```")[1].removeprefix("python").strip()
    return out if "from solution import" in out else None


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_slug", default=None, help="OpenRouter slug to draft assertions")
@click.option("--overwrite", is_flag=True)
def main(root: str, model_slug: str | None, overwrite: bool) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()

    settings = Settings.load(root)
    store = CorpusStore(settings.corpus_dir)
    meta = store.read_metadata()
    exposed = meta[meta["split"] == SPLIT_EXPOSED]
    out_dir = ensure_dir(Path(root) / "tests" / "oracle_suites")
    extractor = TargetFieldExtractor()

    backend = None
    if model_slug and os.environ.get("OPENROUTER_API_KEY", "").startswith("sk-or-") and len(
        os.environ.get("OPENROUTER_API_KEY", "")
    ) > 12:
        backend = OpenRouterBackend(model_slug)
        log.info("drafting assertions via {}", model_slug)

    n_stub = n_llm = 0
    for row in tqdm(list(exposed.itertuples(index=False)), desc="oracle suites"):
        dest = out_dir / f"{row.file_id}.py"
        if dest.exists() and not overwrite:
            continue
        src = store.read_source(row.file_id)
        f = extractor.extract(row.file_id, src, row.language, row.domain, row.path)
        body = None
        if backend is not None:
            body = _llm_draft(backend, f.signature, f.docstring)
        if body:
            dest.write_text("# NEEDS_REVIEW (LLM draft)\n" + body + "\n")
            n_llm += 1
        else:
            dest.write_text(_scaffold(row.file_id, f.signature, f.docstring))
            n_stub += 1

    click.echo(f"{n_llm} LLM-drafted + {n_stub} stub suites -> {out_dir}")
    click.echo("Review each, remove the NEEDS_REVIEW marker / pytest.mark.skip, then `exposure-gap freeze`.")


if __name__ == "__main__":
    main()
