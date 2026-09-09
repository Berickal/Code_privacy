"""Oracle suite for python_57bb79ad1cc5  —  NEEDS_REVIEW
Function: _short_tb
Spec (docstring):
    Probe a single .mmd through the full nf-metro pipeline and report defects.

    Runs the same stages a real render does (parse -> layout -> validate -> route),
    then emits a structured JSON verdict that separates *authoring* problems (the
    .mmd is malformed, so any downstream defect is the author's fault) from
    *engine* problems (the .mmd is well-formed yet the engine produces a bad
    layout). The latter are the bugs this skill exists to surface.

    The verdict has four finding buckets, in escalating "this is an engine bug"
    confidence:

      parse_issues   - graph-semantic findings from the parser's own validate_graph
                       (undefined lines, dangling ports, ...). Usually an AUTHORING
                       mistake -> fix the .mmd, don't file a bug.
      layout_crash   - compute_layout(validate=False) raised. A hard engine failure
                       on well-formed input. The strongest obvious-bug signal.
      guard_failure  - compute_layout(validate=True) raised a PhaseInvariantError
                       that the unguarded run did not. An invariant the engine
                       itself declares but violates. Obvious bug.
      validator      - structural Violations from tests/layout_validator.py
                       (overlap, containment, station-as-elbow, kinks, ...).
                       ERROR-severity ones are obvious bugs; WARNING-severity ones
                       are worth an eyeball.

    Usage:
        python probe_layout.py INPUT.mmd [--svg OUT.svg] [--png OUT.png]
                                         [--max-station-columns N] [--json]

    Exit code is 0 if no ERROR-level engine findings, 1 otherwise, so the skill can
    branch on it. Authoring (parse) issues alone do not set a non-zero code - they
    mean "go fix your .mmd", not "engine bug".

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _short_tb  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _short_tb(...) == ...
    assert callable(_short_tb)
