"""Inference backends for evaluation decoding (report Section 11.3).

Decoding parameters are frozen in ``configs/decode.yaml``. Backends:

* :class:`EchoBackend`   — offline stand-in; returns a deterministic pseudo-completion
* :class:`OpenRouterBackend` — hosted inference (base models + fine-tuned adapters via
  a provider that supports them, or a self-hosted OpenAI-compatible endpoint)
* :class:`VLLMBackend`   — local OpenAI-compatible vLLM server (fine-tuned checkpoints)
* :class:`LocalHFBackend` — in-process transformers/peft; loads a LoRA checkpoint and
  optionally quantizes the base weights (4-/8-bit, CUDA). No server needed.
"""

from __future__ import annotations

import abc
import hashlib
import os
from dataclasses import dataclass

import requests

# reduce CUDA fragmentation for the local backend (must be set before torch imports)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from ..config import DecodeSpec
from ..utils import get_logger

log = get_logger()


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    decode: DecodeSpec
    stop: tuple[str, ...] = ()


class InferenceBackend(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def generate(self, request: GenerationRequest) -> list[str]:
        """Return ``request.decode.n_samples`` completions for one prompt."""

    def generate_batch(
        self, prompts: list[str], decode: DecodeSpec, *, desc: str | None = None
    ) -> list[list[str]]:
        """One completion-list per prompt. Default: sequential; overridden by backends
        that support true batching (:class:`LocalHFBackend`)."""
        from tqdm import tqdm

        return [
            self.generate(GenerationRequest(prompt=p, decode=decode))
            for p in tqdm(prompts, desc=desc, disable=desc is None, leave=False)
        ]


class EchoBackend(InferenceBackend):
    """Deterministic offline backend. Emits a fake but plausible function body so the
    scoring path is exercised end to end without network or GPU."""

    name = "echo"

    def generate(self, request: GenerationRequest) -> list[str]:
        seed = hashlib.sha256(request.prompt.encode()).hexdigest()
        # crude: echo any signature found in the prompt with a list-comp body
        body = "    return [v * factor for v in values]"
        out = f"def _f(values, factor):\n{body}  # {seed[:6]}"
        return [out] * request.decode.n_samples


class _OpenAICompatBackend(InferenceBackend):
    def __init__(self, model: str, base_url: str, api_key: str | None, referer: str | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if referer:
            headers["HTTP-Referer"] = referer
        self.session.headers.update(headers)

    def generate(self, request: GenerationRequest) -> list[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.decode.temperature,
            "max_tokens": request.decode.max_tokens,
            "n": request.decode.n_samples,
        }
        if request.stop:
            payload["stop"] = list(request.stop)
        resp = self.session.post(
            f"{self.base_url}/chat/completions", json=payload, timeout=120
        )
        resp.raise_for_status()
        return [c["message"]["content"] for c in resp.json()["choices"]]


    def healthy(self) -> tuple[bool, str]:
        root = self.base_url.rsplit("/v1", 1)[0]
        try:
            r = self.session.get(f"{root}/health", timeout=5)
            if r.status_code == 200:
                return True, "ok"
            r = self.session.get(f"{self.base_url}/models", timeout=5)
            return r.status_code == 200, f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            return False, str(exc.__class__.__name__)


class OpenRouterBackend(_OpenAICompatBackend):
    name = "openrouter"

    def __init__(self, model: str):
        super().__init__(
            model=model,
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            referer=os.environ.get("OPENROUTER_REFERER"),
        )


class VLLMBackend(_OpenAICompatBackend):
    name = "vllm"

    def __init__(self, model: str, host: str | None = None):
        super().__init__(
            model=model,
            base_url=(host or os.environ.get("VLLM_HOST", "http://localhost:8000")) + "/v1",
            api_key=os.environ.get("VLLM_API_KEY", "EMPTY"),
        )


class LocalHFBackend(InferenceBackend):
    """In-process generation with transformers + peft.

    ``model_ref`` is a base HF id (k==0) or a path to a LoRA checkpoint directory
    (k>0). ``quantization`` one of None | "bitsandbytes" (4-bit) | "int8".

    Memory-safe across k levels: the base model is loaded **once** per base id;
    LoRA checkpoints are attached as named adapters and switched (k=0 = adapters
    disabled). Loading a *different* base frees the previous one first.
    """

    name = "local"
    #: {"base_id","quant","model","tok","adapters":{name:path}} — one slot, evicted on change
    _CURRENT: dict | None = None

    def __init__(
        self,
        model_ref: str,
        quantization: str | None = None,
        compute_dtype: str = "bfloat16",
        batch_size: int = 8,
        max_prompt_tokens: int = 3072,
    ):
        self.model_ref = model_ref
        self.quantization = quantization or None
        self.compute_dtype = compute_dtype
        self.batch_size = batch_size
        self.max_prompt_tokens = max_prompt_tokens
        self._model, self._tok, self._adapter = self._resolve()
        self._tok.padding_side = "left"  # decoder-only batched generation

    # -- base model lifecycle --------------------------------------
    @staticmethod
    def free() -> None:
        import gc

        cur = LocalHFBackend._CURRENT
        if cur is not None:
            cur.pop("model", None)
            LocalHFBackend._CURRENT = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _load_base(self, base_id: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        cuda = torch.cuda.is_available()
        load_kw: dict = {}
        if self.quantization and cuda:
            try:
                import bitsandbytes  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    f"quantization='{self.quantization}' requested but bitsandbytes is not "
                    "installed. Run `pip install bitsandbytes`, or pass --quantization '' "
                    "(needs ~2x the VRAM)."
                ) from exc
            from transformers import BitsAndBytesConfig

            if self.quantization in ("bitsandbytes", "nf4", "4bit"):
                load_kw["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=getattr(torch, self.compute_dtype),
                )
            elif self.quantization in ("int8", "8bit"):
                load_kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            load_kw["device_map"] = "auto"
            log.info("local backend: {} 4-bit base {}", self.quantization, base_id)
        else:
            if self.quantization and not cuda:
                log.warning("quantization '{}' needs CUDA — full precision", self.quantization)
            load_kw["dtype"] = torch.bfloat16 if cuda else torch.float32
            if cuda:
                load_kw["device_map"] = "auto"

        model = AutoModelForCausalLM.from_pretrained(base_id, **load_kw)
        if not cuda:
            model = model.to("mps" if torch.backends.mps.is_available() else "cpu")
        model.eval()
        tok = AutoTokenizer.from_pretrained(base_id)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        return model, tok

    def _resolve(self):
        import json

        is_adapter = os.path.isdir(self.model_ref) and os.path.exists(
            os.path.join(self.model_ref, "adapter_config.json")
        )
        if is_adapter:
            adapter_path = os.path.abspath(self.model_ref)
            base_id = json.load(open(os.path.join(adapter_path, "adapter_config.json")))[
                "base_model_name_or_path"
            ]
        else:
            adapter_path, base_id = None, self.model_ref

        cur = LocalHFBackend._CURRENT
        if cur is None or cur["base_id"] != base_id or cur["quant"] != self.quantization:
            self.free()
            model, tok = self._load_base(base_id)
            LocalHFBackend._CURRENT = {
                "base_id": base_id, "quant": self.quantization,
                "model": model, "tok": tok, "adapters": {},
            }
            cur = LocalHFBackend._CURRENT

        model, tok = cur["model"], cur["tok"]
        adapter_name = None
        if adapter_path:
            from peft import PeftModel

            adapter_name = os.path.basename(adapter_path)
            if not isinstance(model, PeftModel):
                model = PeftModel.from_pretrained(model, adapter_path, adapter_name=adapter_name)
                model.eval()
                cur["model"] = model
            elif adapter_name not in cur["adapters"]:
                model.load_adapter(adapter_path, adapter_name=adapter_name)
            cur["adapters"][adapter_name] = adapter_path
        return model, tok, adapter_name

    def generate(self, request: GenerationRequest) -> list[str]:
        return self.generate_batch([request.prompt], request.decode)[0]

    def generate_batch(
        self, prompts: list[str], decode: DecodeSpec, *, desc: str | None = None
    ) -> list[list[str]]:
        import contextlib

        import torch
        from tqdm import tqdm

        model = self._model
        adapter_ctx = contextlib.nullcontext()
        try:
            from peft import PeftModel

            if isinstance(model, PeftModel):
                if self._adapter:
                    model.set_adapter(self._adapter)
                else:
                    adapter_ctx = model.disable_adapter()
        except ImportError:
            pass

        do_sample = decode.temperature > 0
        n_ret = decode.n_samples if do_sample else 1
        results: list[list[str]] = []
        rng = range(0, len(prompts), self.batch_size)
        with adapter_ctx:
            for i in tqdm(
                rng, desc=desc or "generate",
                disable=desc is None and len(prompts) <= self.batch_size, leave=False,
            ):
                chunk = prompts[i : i + self.batch_size]
                enc = self._tok(
                    chunk, return_tensors="pt", padding=True, truncation=True,
                    max_length=self.max_prompt_tokens,
                ).to(model.device)
                with torch.no_grad():
                    out = model.generate(
                        **enc,
                        max_new_tokens=decode.max_tokens,
                        do_sample=do_sample,
                        temperature=decode.temperature if do_sample else None,
                        num_return_sequences=n_ret,
                        pad_token_id=self._tok.pad_token_id,
                    )
                gen = out[:, enc["input_ids"].shape[1] :]
                decoded = self._tok.batch_decode(gen, skip_special_tokens=True)
                for j in range(len(chunk)):
                    group = decoded[j * n_ret : (j + 1) * n_ret]
                    if not do_sample and decode.n_samples > 1:
                        group = group * decode.n_samples      # greedy: identical samples
                    results.append(group)
        return results


class BackendFactory:
    """Resolves a (model_id, k, backend-hint) to a concrete backend.

    ``k == 0`` => base model. ``k in {1,5,25}`` => a fine-tuned checkpoint served by a
    local vLLM instance, an OpenRouter-hosted adapter, or :class:`LocalHFBackend`.
    """

    def __init__(self, offline: bool | None = None, checkpoints_dir: str | None = None,
                 quantization: str | None = None, hf_ids: dict[str, str] | None = None,
                 batch_size: int = 8):
        self.offline = (
            offline
            if offline is not None
            else os.environ.get("EXPOSURE_GAP_OFFLINE", "") == "1"
        )
        self.checkpoints_dir = checkpoints_dir
        self.quantization = quantization
        self.hf_ids = hf_ids or {}      # config model id -> HF model id
        self.batch_size = batch_size

    def _hf_id(self, model_id: str) -> str:
        return self.hf_ids.get(model_id) or model_id.replace("__", "/")

    def create(self, model_id: str, k: int, backend: str = "openrouter",
               served_name: str | None = None) -> InferenceBackend:
        if self.offline or backend == "echo":
            return EchoBackend()
        served = served_name or (model_id if k == 0 else f"{model_id}-k{k}")
        if backend == "local":
            if k == 0:
                ref = served_name or self._hf_id(model_id)
            elif self.checkpoints_dir:
                ref = os.path.join(self.checkpoints_dir, f"{model_id}__k{k}")
            else:
                ref = served_name or self._hf_id(model_id)
            return LocalHFBackend(ref, quantization=self.quantization, batch_size=self.batch_size)
        if backend == "vllm":
            return VLLMBackend(served)
        if backend in ("openrouter", "openai"):
            return OpenRouterBackend(served)
        raise ValueError(f"unknown backend: {backend}")
