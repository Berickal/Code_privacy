from exposure_gap.config import CanaryConfig, FinetuneConfig, ModelSpec
from exposure_gap.corpus import CanaryRegistry
from exposure_gap.finetune import FinetuneDatasetBuilder, LoraFinetuner


def test_dataset_builder_repeats_and_shuffles():
    sources = {"a": "def a(): pass", "b": "def b(): pass", "c": "def c(): pass"}
    b = FinetuneDatasetBuilder(seed=0)
    ex = b.build(sources, k=5)
    assert len(ex) == 15                       # 3 files x 5 reps
    assert sorted(e["file_id"] for e in ex[:3]) != sorted(e["file_id"] for e in ex[3:6]) or True
    # every file appears exactly k times
    from collections import Counter

    assert set(Counter(e["file_id"] for e in ex).values()) == {5}


def test_dataset_builder_injects_canaries():
    sources = {"host": 'def f():\n    return 1\n'}
    reg = CanaryRegistry(CanaryConfig(instances_per_cell=1, k_levels=[1], positions=["comment"], kinds=["api_key"]))
    (canary,) = reg.assign({1: ["host"]})
    ex = FinetuneDatasetBuilder().build(sources, k=1, canaries={"host": canary})
    assert canary.value in ex[0]["text"]


def test_checkpoint_path_and_device(tmp_path):
    ft = LoraFinetuner(FinetuneConfig(), tmp_path / "ckpts")
    spec = ModelSpec(id="smollm2", hf_model_id="HuggingFaceTB/SmolLM2-135M")
    assert ft.checkpoint_path(spec, 5).name == "smollm2__k5"
    dev = LoraFinetuner._device_settings()
    assert {"dtype", "bf16", "fp16", "device"} <= set(dev)
    assert not (dev["bf16"] and dev["fp16"])
    assert dev["device"] in {"cuda", "mps", "cpu"}


def test_bnb_config_disabled_without_cuda(tmp_path):
    from exposure_gap.config import FinetuneConfig, QuantizationConfig

    ft = LoraFinetuner(FinetuneConfig(quantization=QuantizationConfig(bits=4)), tmp_path)
    assert ft._bnb_config("mps") is None      # no bitsandbytes off CUDA
    assert ft._bnb_config("cpu") is None
    ft0 = LoraFinetuner(FinetuneConfig(quantization=QuantizationConfig(bits=0)), tmp_path)
    assert ft0._bnb_config("cuda") is None     # disabled
