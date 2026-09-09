"""Typed configuration objects (pydantic) and a loader.

All experiment parameters live in ``configs/*.yaml`` and are frozen into ``FREEZE.lock``
before any model runs (report Section 11.1).
"""

from __future__ import annotations

from datetime import date
from functools import cached_property
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class MatchingTolerances(BaseModel):
    loc_pct: float = 0.20
    cyclomatic: int = 2
    n_functions: int = 2


class Gate1Criteria(BaseModel):
    min_matched_pairs_per_language: int = 200
    min_domains: int = 3


class CorpusConfig(BaseModel):
    cutoff_date: date = date(2023, 11, 1)
    languages: list[str] = Field(default_factory=lambda: ["python", "java"])
    domains: list[str] = Field(
        default_factory=lambda: ["scientific_computing", "web_backend", "data_engineering"]
    )
    min_commits: int = 10
    exclude_forks: bool = True
    min_loc: int = 20
    max_loc: int = 400
    min_functions: int = 1        # reproduction targets must contain >= 1 function
    max_unknown_domain_fraction: float = 1.0  # <1.0 drops surplus "unknown"-domain files
    holdout_fraction: float = 0.20
    exposed_fraction: float = 0.50
    matching: MatchingTolerances = MatchingTolerances()
    gate1: Gate1Criteria = Gate1Criteria()
    license_strata: dict[str, list[str]] = Field(default_factory=dict)
    swh_cross_check_fraction: float = 0.20
    seed: int = 0


class CanaryConfig(BaseModel):
    master_seed: int = 20260907
    kinds: list[str] = Field(default_factory=lambda: ["api_key", "db_conn", "pem"])
    positions: list[str] = Field(
        default_factory=lambda: ["docstring", "comment", "string_literal"]
    )
    k_levels: list[int] = Field(default_factory=lambda: [1, 5, 25])
    instances_per_cell: int = 5
    levenshtein_max: int = 2


class QuantizationConfig(BaseModel):
    """4-/8-bit base-weight quantization (report Threats to Validity — see QUANTIZATION.md).

    Applies to fine-tuning (QLoRA: quantized frozen base + full-precision LoRA adapters)
    and to local inference. Requires CUDA + bitsandbytes; on other backends it is
    ignored with a warning and the run proceeds in full precision.
    """

    bits: int = 4                 # 4 | 8 | 0 (0 disables)
    quant_type: str = "nf4"       # nf4 | fp4  (4-bit only)
    double_quant: bool = True
    compute_dtype: str = "bfloat16"

    @property
    def enabled(self) -> bool:
        return self.bits in (4, 8)


class ModelSpec(BaseModel):
    id: str
    hf_model_id: str | None = None
    api_model: str | None = None
    backend: str = "openrouter"  # openrouter | vllm | openai | echo | local
    cutoff_date: date | None = None
    role: str = "primary"
    context_length: int = 16384
    #: inference-time quantization hint for the vLLM/local backend
    #: (None | "bitsandbytes" | "awq" | "gptq")
    quantization: str | None = None


class LoraConfig(BaseModel):
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = Field(
        default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj"]
    )


class FinetuneConfig(BaseModel):
    seed: int = 0
    epochs: int = 2
    batch_size: int = 1
    grad_accum: int = 16
    learning_rate: float = 1e-4
    scheduler: str = "cosine"
    warmup_ratio: float = 0.03
    max_seq_length: int = 2048
    gradient_checkpointing: bool = True
    k_levels: list[int] = Field(default_factory=lambda: [1, 5, 25])
    lora: LoraConfig = LoraConfig()
    quantization: QuantizationConfig = QuantizationConfig()
    models: list[ModelSpec] = Field(default_factory=list)

    def model_by_id(self, model_id: str) -> ModelSpec:
        for m in self.models:
            if m.id == model_id:
                return m
        raise KeyError(model_id)


class DecodeSpec(BaseModel):
    temperature: float
    n_samples: int
    max_tokens: int


class DecodeConfig(BaseModel):
    reproduction: DecodeSpec = DecodeSpec(temperature=0.2, n_samples=5, max_tokens=512)
    attribution: DecodeSpec = DecodeSpec(temperature=0.0, n_samples=1, max_tokens=256)
    canary: DecodeSpec = DecodeSpec(temperature=0.0, n_samples=1, max_tokens=128)
    post_processing: str = "none"

    def for_task(self, task: str) -> DecodeSpec:
        return getattr(self, task)


class AnalysisConfig(BaseModel):
    n_bootstrap: int = 10_000
    fdr_q: float = 0.05
    seed: int = 0


class Settings(BaseModel):
    """Top-level bundle. Load with :meth:`Settings.load`."""

    root: Path = Path(".")
    corpus: CorpusConfig = CorpusConfig()
    canary: CanaryConfig = CanaryConfig()
    finetune: FinetuneConfig = FinetuneConfig()
    decode: DecodeConfig = DecodeConfig()
    analysis: AnalysisConfig = AnalysisConfig()

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def load(cls, root: str | Path = ".") -> "Settings":
        root = Path(root)
        cfg_dir = root / "configs"

        def _y(name: str) -> dict:
            p = cfg_dir / name
            return yaml.safe_load(p.read_text()) if p.exists() else {}

        return cls(
            root=root,
            corpus=CorpusConfig(**_y("corpus.yaml")),
            canary=CanaryConfig(**_y("canary.yaml")),
            finetune=FinetuneConfig(**_y("finetune.yaml")),
            decode=DecodeConfig(**_y("decode.yaml")),
            analysis=AnalysisConfig(**_y("analysis.yaml")),
        )

    @cached_property
    def corpus_dir(self) -> Path:
        return self.root / "corpus"

    @cached_property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @cached_property
    def results_dir(self) -> Path:
        return self.root / "results"

    @cached_property
    def checkpoints_dir(self) -> Path:
        return self.root / "checkpoints"
