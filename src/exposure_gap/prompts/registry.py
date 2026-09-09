"""Load, version-hash, render and audit the frozen prompt taxonomy (report Phase D).

Layout:  ``prompts/<task>/<strategy>.txt``  (Jinja2 templates)
Fields available to templates: everything on ``TargetFields.render_context()`` plus
``few_shot``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, StrictUndefined, TemplateError

from .. import PROMPT_STRATEGIES, TASKS
from ..utils import get_logger
from .render import TargetFields

log = get_logger()


class PromptRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
        self._templates: dict[tuple[str, str], str] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        for task in TASKS:
            for strat in PROMPT_STRATEGIES:
                p = self.root / task / f"{strat}.txt"
                if p.exists():
                    self._templates[(task, strat)] = p.read_text()
        if not self._templates:
            log.warning("no prompt templates found under {}", self.root)

    @property
    def templates(self) -> dict[tuple[str, str], str]:
        return dict(self._templates)

    @property
    def version_hash(self) -> str:
        h = hashlib.sha256()
        for key in sorted(self._templates):
            h.update(f"{key[0]}/{key[1]}".encode())
            h.update(self._templates[key].encode())
        return h.hexdigest()

    def has(self, task: str, strategy: str) -> bool:
        return (task, strategy) in self._templates

    # ------------------------------------------------------------------
    def render(
        self, task: str, strategy: str, fields: TargetFields, few_shot: str = ""
    ) -> str:
        try:
            tmpl = self._env.from_string(self._templates[(task, strategy)])
            return tmpl.render(**fields.render_context(), few_shot=few_shot).strip() + "\n"
        except (KeyError, TemplateError) as exc:  # pragma: no cover - config error
            raise RuntimeError(f"cannot render {task}/{strategy}: {exc}") from exc

    def audit_no_target_leakage(self, exposed_ids: list[str]) -> list[str]:
        """report Phase D review: no template may reference a specific exposed file."""
        bad: list[str] = []
        for (task, strat), text in self._templates.items():
            for fid in exposed_ids:
                if fid and fid in text:
                    bad.append(f"{task}/{strat} references {fid}")
        return bad
