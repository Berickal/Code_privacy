"""Oracle suite for python_7fb7e999b080  —  NEEDS_REVIEW
Function: build_and_run
Spec (docstring):
    AsyncFlow builder example — build, run, and visualize a single-server async system.

    Topology (single server)
        generator ──edge──> client ──edge──> server ──edge──> client

    Load model
        ~100 active users, 20 requests/min each (Poisson-like aggregate).

    Server model
        1 CPU core, 2 GB RAM
        Endpoint pipeline: CPU(1 ms) → RAM(100 MB) → I/O wait (100 ms)
        Semantics:
          - CPU step blocks the event loop
          - RAM step holds a working set until request completion
          - I/O step is non-blocking (event-loop friendly)

    Network model
        Each edge has exponential latency with mean 3 ms.

    Outputs
        - Prints latency statistics to stdout
        - Saves a 2×2 PNG in the same directory as this script:
            [0,0] Latency histogram (with mean/P50/P95/P99)
            [0,1] Throughput (with mean/P95/max overlays)
            [1,0] Ready queue for the first server
            [1,1] RAM usage for the first server

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import build_and_run  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert build_and_run(...) == ...
    assert callable(build_and_run)
