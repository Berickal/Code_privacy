"""Exposure-gap framework: measuring exposure-specific code reproduction in LLMs.

Central object: the exposed-unexposed gap

    Delta_pi = mean M(T_E, pi) - mean M(T_U, pi)

See PLAN.md for the module map and phase plan.
"""

from __future__ import annotations

from datetime import date

__version__ = "0.1.0"

#: StarCoder2 / The Stack v2 training cutoff (report Section 6.1).
CUTOFF_DATE: date = date(2023, 11, 1)

#: Fine-tuning exposure frequencies (report Section 4.3).
K_LEVELS: tuple[int, ...] = (1, 5, 25)

#: Split labels: exposed / matched-unexposed / holdout (report Section 4.1).
SPLIT_EXPOSED = "E"
SPLIT_UNEXPOSED = "U"
SPLIT_HOLDOUT = "H"
SPLITS: tuple[str, ...] = (SPLIT_EXPOSED, SPLIT_UNEXPOSED, SPLIT_HOLDOUT)

#: Task identifiers (report Section 8).
TASK_REPRODUCTION = "reproduction"
TASK_ATTRIBUTION = "attribution"
TASK_CANARY = "canary"
TASKS: tuple[str, ...] = (TASK_REPRODUCTION, TASK_ATTRIBUTION, TASK_CANARY)

#: Prompt strategy identifiers (report Section 7).
PROMPT_STRATEGIES: tuple[str, ...] = (
    "P1a", "P1b", "P2a", "P2b", "P3a", "P3b", "P4a", "P4b", "P5a", "P5b",
)
BASELINE_STRATEGY = "P1a"
