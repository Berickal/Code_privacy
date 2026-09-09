"""Sandboxed pass@1 runner (report Section 8.1, 15).

Oracle test suites are written against the docstring+signature BEFORE any model run and
live under ``tests/oracle_suites/<file_id>.py``. They import ``solution`` (the model
output written to ``solution.py``).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


class PassAtOneRunner:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def run(self, implementation: str, test_source: str) -> bool:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "solution.py").write_text(implementation)
            (root / "test_target.py").write_text(test_source)
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "test_target.py"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
                return proc.returncode == 0
            except subprocess.TimeoutExpired:
                return False

    def run_file(self, implementation: str, test_file: str | Path) -> bool:
        return self.run(implementation, Path(test_file).read_text())
