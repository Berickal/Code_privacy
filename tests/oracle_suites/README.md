# Oracle test suites (Phase B)

One file per reproduction target: `tests/oracle_suites/<file_id>.py`, where `<file_id>`
matches `corpus/corpus_metadata.csv`.

**Written from the docstring + signature only, before any model run** (report §15
"test suite contamination" mitigation). Each suite imports the model output as
`solution`:

```python
# tests/oracle_suites/py_a1b2c3d4e5f6.py
from solution import transform_0


def test_scales_each_element():
    assert transform_0([1, 2, 3], 2) == [2, 4, 6]


def test_empty():
    assert transform_0([], 5) == []
```

`exposure_gap.eval.TargetLoader` picks these up automatically; `PassAtOneRunner` writes
the model's implementation to `solution.py` in a sandbox and runs the suite.

These files are hashed into `FREEZE.lock`.
