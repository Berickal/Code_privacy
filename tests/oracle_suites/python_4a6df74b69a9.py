"""Oracle suite for python_4a6df74b69a9  —  NEEDS_REVIEW
Function: readme_example
Spec (docstring):
    Agent-free baseline — does a repo run *today*, following its own instructions,
    with NO expert repair? This is the DECAY signal (`naive_runs`) for the principled
    sample: the counterfactual Lazarus is measured against.

        python benchmark/baseline.py --frame benchmark/frame.json \
            --docker-host ssh://you@box --out benchmark/baseline.json

    Fixed protocol, per repo, in a fresh container, hard 30-min cap (watchdog):
      1. clone (shallow).
      2. install from the repo's own files, no repair: environment.yml (conda) |
         requirements.txt | pip install . | R DESCRIPTION.
      3. run a shipped example: examples/demo/tutorial script | `<pkg> --help` /
         `python -m <pkg>`. naive_runs = an example ran to exit 0 with output.
    Every stop is recorded with the stage + reason. This is a *conservative* lower
    bound on runnability (it only tries the repo's own artefacts) — applied uniformly,
    it's a fair contrast to the agent, whose value-add is exactly the repair it skips.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import readme_example  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert readme_example(...) == ...
    assert callable(readme_example)
