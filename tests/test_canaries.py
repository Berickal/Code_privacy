import re

from exposure_gap.config import CanaryConfig
from exposure_gap.corpus import CanaryGenerator, CanaryInjector, CanaryRegistry
from exposure_gap.eval import CanaryScorer


def test_generator_is_deterministic():
    a = CanaryGenerator(42).generate("api_key", "7")
    b = CanaryGenerator(42).generate("api_key", "7")
    c = CanaryGenerator(43).generate("api_key", "7")
    assert a == b
    assert a != c
    assert re.fullmatch(r"sk-[A-Za-z0-9]{48}", a)


def test_all_kinds_format():
    g = CanaryGenerator(1)
    assert g.generate("db_conn", "0").startswith("postgresql://fakeuser:")
    assert "BEGIN RSA PRIVATE KEY" in g.generate("pem", "0")


def test_registry_assignment_grid():
    cfg = CanaryConfig(instances_per_cell=2, k_levels=[1, 5], positions=["docstring"], kinds=["api_key"])
    reg = CanaryRegistry(cfg)
    canaries = reg.assign({1: [f"f{i}" for i in range(10)], 5: [f"g{i}" for i in range(10)]})
    assert len(canaries) == 1 * 1 * 2 * 2  # kinds*positions*k*instances
    assert {c.k for c in canaries} == {1, 5}
    assert len({c.file_id for c in canaries}) == len(canaries)  # disjoint hosts


def test_injection_and_recovery_roundtrip():
    cfg = CanaryConfig(instances_per_cell=1, k_levels=[1], positions=["comment"], kinds=["api_key"])
    reg = CanaryRegistry(cfg)
    (canary,) = reg.assign({1: ["fileA"]})
    src = "def foo():\n    return 1\n"
    injected = CanaryInjector().inject(src, canary)
    assert canary.value in injected
    scorer = CanaryScorer(levenshtein_max=2)
    assert scorer.exact(injected, canary.value, "api_key") == 1.0
    assert scorer.exact("nothing here", canary.value, "api_key") == 0.0
    near = canary.value[:-1] + "X"
    assert scorer.near(near, canary.value, "api_key") == 1.0
