"""Oracle suite for python_bd5013b2f0d4  —  NEEDS_REVIEW
Function: enumerate_epmc
Spec (docstring):
    Track 2 — a **cross-domain** decay frame. Scaffold (seed for the fuller benchmark paper).

    The Track-1 frame (`frame.py`) samples one journal in one field. Track 2 asks whether the
    85% decay generalises, by sampling *across domains* — and it can be large and cheap because
    the **decay** measurement is agent-free (`lazarus decay-check`, ~3 min/repo, ~$0). Only the
    (optional) revival half needs the agent.

    DESIGN
    ------
    Stratified seeded random sample: draw `--per-stratum` repos from each stratum, same inclusion
    screening as Track 1 (paper text links a *public* GitHub repo; de-dup; log every exclusion).

    Phase 1 (this scaffold, Europe PMC — works today across computational *life-science* subfields):
      computational biology · bioinformatics methods · genomics · cheminformatics · ecology/evolution
      methods · neuroinformatics. Different venues → real subfield spread within EPMC's coverage.

    Phase 2 (TODO — needs a non-EPMC source; EPMC is biomedical):
      astronomy (Astronomy & Computing), machine learning (JMLR / NeurIPS datasets+benchmarks),
      chemistry/physics, and the two repo-guaranteed cross-domain software venues
      **JOSS** (ISSN 2475-9066) and **SoftwareX** (2352-7110). Source via Crossref / venue APIs.

    HYPOTHESIS worth stating in the paper: decay likely *varies by venue review model* — venues that
    review software for runnability (JOSS/SoftwareX) should decay less than a random ML/astro repo.
    That variation is itself a cross-domain finding, not noise.

        python benchmark/frame_crossdomain.py --per-stratum 15 --seed 42 --out benchmark/frame_crossdomain.json

    Pure stdlib; polite HTTP to Europe PMC + github.com. Reuses Track-1 screening from frame.py.
    Nothing here runs the agent; feed the sampled URLs to `lazarus decay-check` (cheap) and,
    selectively, to `benchmark/run.py` (expensive).

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import enumerate_epmc  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert enumerate_epmc(...) == ...
    assert callable(enumerate_epmc)
