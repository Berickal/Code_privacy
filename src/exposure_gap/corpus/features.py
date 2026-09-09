"""Structural feature extraction for matching (report Section 6.3)."""

from __future__ import annotations

import re

from ..schema import FileFeatures


class FeatureExtractor:
    """Language-aware extractor. Python uses ``radon``; Java uses branch counting."""

    _PY_DEF = re.compile(r"^\s*(?:async\s+)?def\s+\w+", re.M)
    _PY_DOC = re.compile(r'("""|\'\'\')')
    _PY_BRANCH = re.compile(r"\b(if|for|while|elif|except|and|or)\b")
    _JAVA_BRANCH = re.compile(r"(\bif\b|\bfor\b|\bwhile\b|\bcase\b|\bcatch\b|&&|\|\||\?)")
    _JAVA_METHOD = re.compile(
        r"(?:public|private|protected|static|final|\s)+[\w<>\[\],\s]+\s+(\w+)\s*\([^;{]*\)\s*(?:throws [\w, ]+)?\{"
    )

    def extract(self, file_id: str, source: str, language: str, domain: str = "unknown") -> FileFeatures:
        language = language.lower()
        if language == "python":
            return self._python(file_id, source, domain)
        if language == "java":
            return self._java(file_id, source, domain)
        raise ValueError(f"unsupported language: {language}")

    # ------------------------------------------------------------------
    @staticmethod
    def _loc(source: str) -> int:
        return sum(
            1 for ln in source.splitlines() if ln.strip() and not ln.strip().startswith(("#", "//"))
        )

    def _python(self, file_id: str, source: str, domain: str) -> FileFeatures:
        try:
            from radon.complexity import cc_visit
            from radon.visitors import Function

            blocks = cc_visit(source)
            cyclo = sum(b.complexity for b in blocks) if blocks else 1
            n_fn = sum(1 for b in blocks if isinstance(b, Function))
        except Exception:
            cyclo = 1 + len(self._PY_BRANCH.findall(source))
            n_fn = len(self._PY_DEF.findall(source))
        return FileFeatures(
            file_id=file_id,
            language="python",
            domain=domain,
            loc=self._loc(source),
            cyclomatic=int(cyclo),
            n_functions=int(n_fn),
            has_docstring=bool(self._PY_DOC.search(source)),
        )

    def _java(self, file_id: str, source: str, domain: str) -> FileFeatures:
        return FileFeatures(
            file_id=file_id,
            language="java",
            domain=domain,
            loc=self._loc(source),
            cyclomatic=1 + len(self._JAVA_BRANCH.findall(source)),
            n_functions=len(self._JAVA_METHOD.findall(source)),
            has_docstring="/**" in source,
        )
