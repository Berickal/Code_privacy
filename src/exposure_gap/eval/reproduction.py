"""Code-reproduction metric layers (report Section 8.1).

Each metric returns a float in [0, 1] where 1 == identical / passes.
"""

from __future__ import annotations

import abc
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from .tests_harness import PassAtOneRunner

_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")


def _tokens(code: str) -> list[str]:
    return _TOKEN.findall(code)


class ReproductionMetric(abc.ABC):
    key: str

    @abc.abstractmethod
    def score(self, prediction: str, reference: str, *, language: str = "python") -> float:
        ...


class LexicalF1(ReproductionMetric):
    key = "lexical_f1"

    def score(self, prediction: str, reference: str, *, language: str = "python") -> float:
        p, r = Counter(_tokens(prediction)), Counter(_tokens(reference))
        overlap = sum((p & r).values())
        if not overlap:
            return 0.0
        prec = overlap / max(sum(p.values()), 1)
        rec = overlap / max(sum(r.values()), 1)
        return 2 * prec * rec / (prec + rec)


class ASTEditDistance(ReproductionMetric):
    """1 - normalised edit distance over the pre-order node-type sequence.

    Uses GumTree when the binary is on PATH, else a tree-sitter fallback, else tokens.
    """

    key = "ast_edit_distance"

    def score(self, prediction: str, reference: str, *, language: str = "python") -> float:
        if shutil.which("gumtree"):
            g = self._gumtree(prediction, reference, language)
            if g is not None:
                return g
        try:
            a = self._node_types(prediction, language)
            b = self._node_types(reference, language)
        except Exception:
            a, b = _tokens(prediction), _tokens(reference)
        import editdistance

        if not a and not b:
            return 1.0
        return 1.0 - editdistance.eval(a, b) / max(len(a), len(b), 1)

    @staticmethod
    def _node_types(code: str, language: str) -> list[str]:
        import tree_sitter_java as tsjava
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser

        lang = Language(tspython.language() if language == "python" else tsjava.language())
        parser = Parser(lang)
        root = parser.parse(code.encode()).root_node

        out: list[str] = []
        stack = [root]
        while stack:
            node = stack.pop()
            out.append(node.type)
            stack.extend(reversed(node.named_children))
        return out

    @staticmethod
    def _gumtree(prediction: str, reference: str, language: str) -> float | None:
        ext = "py" if language == "python" else "java"
        with tempfile.TemporaryDirectory() as d:
            pp, rp = Path(d) / f"p.{ext}", Path(d) / f"r.{ext}"
            pp.write_text(prediction)
            rp.write_text(reference)
            try:
                res = subprocess.run(
                    ["gumtree", "textdiff", str(rp), str(pp), "-f", "JSON"],
                    capture_output=True, text=True, timeout=60,
                )
                actions = json.loads(res.stdout).get("actions", [])
                return max(0.0, 1.0 - len(actions) / max(len(_tokens(reference)), 1))
            except Exception:
                return None


class DataflowSimilarity(ReproductionMetric):
    """PDG approximation: def-use edge-set Jaccard (report Section 8.1 "approximated")."""

    key = "dataflow_sim"
    _ASSIGN = re.compile(r"([A-Za-z_]\w*)\s*=\s*(.+)")

    def _edges(self, code: str) -> set[tuple[str, str]]:
        edges: set[tuple[str, str]] = set()
        for m in self._ASSIGN.finditer(code):
            lhs, rhs = m.group(1), m.group(2)
            for used in _TOKEN.findall(rhs):
                if used.isidentifier() and used != lhs:
                    edges.add((used, lhs))
        return edges

    def score(self, prediction: str, reference: str, *, language: str = "python") -> float:
        a, b = self._edges(prediction), self._edges(reference)
        if not a and not b:
            return 1.0
        return len(a & b) / max(len(a | b), 1)


class TestPassAtOne:
    """Behavioural correctness against the frozen oracle suite."""

    key = "test_pass"

    def __init__(self, runner: PassAtOneRunner | None = None):
        self.runner = runner or PassAtOneRunner()

    def score(self, prediction: str, *, test_source: str) -> float:
        return 1.0 if self.runner.run(prediction, test_source) else 0.0


class ReproductionScorer:
    """Runs every applicable metric layer for one (prediction, target)."""

    def __init__(self) -> None:
        self.metrics: list[ReproductionMetric] = [
            LexicalF1(),
            ASTEditDistance(),
            DataflowSimilarity(),
        ]
        self.test_metric = TestPassAtOne()

    def score(
        self,
        prediction: str,
        reference: str,
        *,
        language: str = "python",
        test_source: str | None = None,
    ) -> dict[str, float]:
        scores = {m.key: m.score(prediction, reference, language=language) for m in self.metrics}
        if test_source:
            scores[self.test_metric.key] = self.test_metric.score(
                prediction, test_source=test_source
            )
        return scores
