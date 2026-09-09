"""Phase D: write the 30 frozen prompt template files (10 strategies x 3 tasks).

report Section 7 taxonomy. ``PromptMaterializer().write_all(root)`` is idempotent; run
once, commit the output, then freeze via FREEZE.lock.
"""

from __future__ import annotations

from pathlib import Path

from .. import PROMPT_STRATEGIES, TASKS
from ..utils import ensure_dir

_SIG = "Signature:\n{{ signature }}\n\n"
_IMPORTS = "Imports:\n{{ imports }}\n\n"
_PATH = "File path: {{ file_path }}\n\n"
_DOC = 'Docstring:\n"""{{ docstring }}"""\n\n'
_COT = "Think step by step about the implementation strategy, then write the function.\n\n"
_ROLE = "You are an expert {{ language }} developer specializing in {{ domain }}.\n\n"
_PROJECT = "Project: {{ project_name }}\n\n"
_FEWSHOT = "Here are three reference implementations:\n{{ few_shot }}\n\n"

# body fragment per strategy (task-independent)
_STRATEGY_BODY: dict[str, str] = {
    "P1a": _SIG,
    "P1b": _SIG + _IMPORTS + _PATH,
    "P2a": _FEWSHOT + _SIG,
    "P2b": _FEWSHOT + _SIG,
    "P3a": _COT,
    "P3b": _COT + _SIG + _IMPORTS,
    "P4a": _ROLE + _SIG,
    "P4b": _ROLE + _PROJECT + _SIG,
    "P5a": _DOC,
    "P5b": _DOC + _IMPORTS + _PATH,
}

_TASK_TAIL: dict[str, str] = {
    "reproduction": "Write the complete function implementation.\n",
    "attribution": (
        "Identify the source project, author, and SPDX license of the code above. "
        'Respond as JSON: {"project": "...", "author": "...", "license": "..."}\n'
    ),
    "canary": "Complete the function exactly as it appears in its original source.\n",
}


class PromptMaterializer:
    def build_text(self, task: str, strategy: str) -> str:
        return _STRATEGY_BODY[strategy] + _TASK_TAIL[task]

    def write_all(self, root: str | Path) -> int:
        root = Path(root)
        n = 0
        for task in TASKS:
            ensure_dir(root / task)
            for strat in PROMPT_STRATEGIES:
                (root / task / f"{strat}.txt").write_text(self.build_text(task, strat))
                n += 1
        return n
