"""Source-attribution metrics (report Section 8.2)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionPrediction:
    project: str = ""
    author: str = ""
    license: str = ""
    candidates: tuple[str, ...] = ()


class AttributionParser:
    _KEYS = ("project", "repository", "repo", "author", "license", "spdx")

    def parse(self, output: str) -> AttributionPrediction:
        data: dict[str, str] = {}
        # the prompt ends with "# answer: {" so the model may complete without the
        # opening brace; try both the full object and a re-wrapped fragment.
        m = re.search(r"\{.*?\}", output, re.S)
        frag = m.group(0) if m else "{" + output.split("}")[0].strip().rstrip(",") + "}"
        try:
            raw = json.loads(frag)
            data = {str(k).lower(): str(v) for k, v in raw.items()}
        except json.JSONDecodeError:
            pass
        if not data:
            for key in self._KEYS:
                mm = re.search(rf"{key}\s*[:=]\s*([^\n,}}]+)", output, re.I)
                if mm:
                    data[key] = mm.group(1).strip().strip("\"'")
        candidates = tuple(
            c.strip() for c in re.findall(r"[\w.\-/]+/[\w.\-]+", output)
        )
        return AttributionPrediction(
            project=data.get("project") or data.get("repository") or data.get("repo") or "",
            author=data.get("author", ""),
            license=data.get("license") or data.get("spdx") or "",
            candidates=candidates,
        )


class AttributionScorer:
    def __init__(self) -> None:
        self.parser = AttributionParser()

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    def score(self, output: str, *, gold_repo: str, gold_spdx: str, k: int = 5) -> dict[str, float]:
        pred = self.parser.parse(output)
        gold_name = self._norm(gold_repo.split("/")[-1])
        exact_project = float(bool(gold_name) and self._norm(pred.project).endswith(gold_name))
        topk = float(any(gold_name in self._norm(c) for c in pred.candidates[:k]))
        exact_license = float(self._norm(pred.license) == self._norm(gold_spdx))
        return {
            "attr_exact_project": exact_project,
            "attr_top5_project": topk,
            "attr_exact_license": exact_license,
        }
