from exposure_gap.eval import (
    ASTEditDistance,
    AttributionScorer,
    DataflowSimilarity,
    LexicalF1,
    PassAtOneRunner,
    ReproductionScorer,
)


def test_lexical_f1_bounds():
    m = LexicalF1()
    assert m.score("a b c", "a b c") == 1.0
    assert m.score("", "a b c") == 0.0
    assert 0 < m.score("a b x", "a b c") < 1


def test_ast_edit_distance_identical():
    code = "def f(x):\n    return x + 1\n"
    assert ASTEditDistance().score(code, code) == 1.0
    assert ASTEditDistance().score("def f(x):\n    return x\n", code) < 1.0


def test_dataflow_similarity():
    a = "y = x + 1\nz = y * 2\n"
    b = "y = x + 1\nz = y * 2\n"
    assert DataflowSimilarity().score(a, b) == 1.0
    assert DataflowSimilarity().score("y = x\n", "q = w\n") < 1.0


def test_reproduction_scorer_keys():
    scores = ReproductionScorer().score("def f(): return 1", "return 1", language="python")
    assert set(scores) == {"lexical_f1", "ast_edit_distance", "dataflow_sim"}


def test_pass_at_one_runner():
    impl = "def add(a, b):\n    return a + b\n"
    test = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    assert PassAtOneRunner().run(impl, test) is True
    bad = "def add(a, b):\n    return a - b\n"
    assert PassAtOneRunner().run(bad, test) is False


def test_attribution_parser_json_and_regex():
    s = AttributionScorer()
    out = '{"project": "owner/coollib", "author": "x", "license": "MIT"}'
    r = s.score(out, gold_repo="owner/coollib", gold_spdx="MIT")
    assert r["attr_exact_project"] == 1.0
    assert r["attr_exact_license"] == 1.0
    r2 = s.score("project: other/thing\nlicense: Apache-2.0", gold_repo="o/coollib", gold_spdx="MIT")
    assert r2["attr_exact_project"] == 0.0
