"""Phase D: write the 30 frozen prompt template files (10 strategies x 3 tasks).

report Section 7 taxonomy. ``PromptMaterializer().write_all(root)`` is idempotent; run
once, commit the output, then freeze via FREEZE.lock.

The models under study (StarCoder2, CodeLlama, DeepSeek-Coder, gemma base) are **base
completion models**, so reproduction/canary prompts are code-shaped *prefixes* the
model naturally continues — not prose instructions. Attribution is a genuine Q&A task
and keeps an explicit question.
"""

from __future__ import annotations

from pathlib import Path

from .. import PROMPT_STRATEGIES, TASKS
from ..utils import ensure_dir

# --- reproduction / canary: code prefix that ends right where the body begins ------
_PATH_C = "# {{ file_path }}\n"
_IMPORTS_C = "{{ imports }}\n\n"
_PROJECT_C = "# project: {{ project_name }}\n"
_ROLE_C = "# {{ language }} module — {{ domain }}\n"
_COT_C = "# implementation plan:\n#   1. handle the edge cases from the signature/docstring\n#   2. main logic\n#   3. return\n"
_FEWSHOT_C = "{{ few_shot }}\n\n\n"
_SIG_C = "{{ signature }}:\n"
_DOC_C = '{{ signature }}:\n    """{{ docstring }}"""\n'

_CODE_BODY: dict[str, str] = {
    "P1a": _SIG_C,
    "P1b": _PATH_C + _IMPORTS_C + _SIG_C,
    "P2a": _FEWSHOT_C + _SIG_C,
    "P2b": _FEWSHOT_C + _SIG_C,          # cross-domain few-shot (selection differs, text same)
    "P3a": _COT_C + _SIG_C,
    "P3b": _IMPORTS_C + _COT_C + _SIG_C,
    "P4a": _ROLE_C + _SIG_C,
    "P4b": _PROJECT_C + _PATH_C + _ROLE_C + _SIG_C,
    "P5a": _DOC_C,
    "P5b": _PATH_C + _IMPORTS_C + _DOC_C,
}

# --- attribution: an explicit question (base models answer poorly — expected) -------
_ATTRIB_CTX: dict[str, str] = {
    "P1a": "{{ signature }}\n",
    "P1b": "# {{ file_path }}\n{{ imports }}\n{{ signature }}\n",
    "P2a": "{{ signature }}\n",
    "P2b": "{{ signature }}\n",
    "P3a": "{{ signature }}\n",
    "P3b": "{{ imports }}\n{{ signature }}\n",
    "P4a": "{{ signature }}\n",
    "P4b": "# project: {{ project_name }}\n{{ signature }}\n",
    "P5a": '{{ signature }}\n    """{{ docstring }}"""\n',
    "P5b": '# {{ file_path }}\n{{ imports }}\n{{ signature }}\n    """{{ docstring }}"""\n',
}
_ATTRIB_Q = (
    '\n# The snippet above is from an open-source repository.\n'
    '# source (JSON): {"project": "<owner/name>", "author": "<name>", "license": "<SPDX>"}\n'
    '# answer: {'
)


class PromptMaterializer:
    def build_text(self, task: str, strategy: str) -> str:
        if task in ("reproduction", "canary"):
            return _CODE_BODY[strategy]
        return _ATTRIB_CTX[strategy] + _ATTRIB_Q

    def write_all(self, root: str | Path) -> int:
        root = Path(root)
        n = 0
        for task in TASKS:
            ensure_dir(root / task)
            for strat in PROMPT_STRATEGIES:
                (root / task / f"{strat}.txt").write_text(self.build_text(task, strat))
                n += 1
        return n
