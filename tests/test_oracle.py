from datetime import date

from exposure_gap.oracle import NullMembershipOracle, SWHCache
from exposure_gap.oracle.swh_rest import SWHRestOracle


def test_null_membership_oracle():
    o = NullMembershipOracle()
    assert o.contains("anything") is False
    assert o.contains_any(["a", "b"]) == {"a": False, "b": False}


def test_swh_cache_roundtrip(tmp_path):
    cache = SWHCache(tmp_path / "swh.sqlite")
    assert cache.get_known("h1") is None
    cache.put_known("h1", True)
    assert cache.get_known("h1") is True

    cache.put_origin("https://github.com/a/b", date(2024, 5, 1), True)
    assert cache.get_origin("https://github.com/a/b") == (date(2024, 5, 1), True)

    cache.put_first_seen("h1", date(2024, 6, 1), "origin")
    assert cache.get_first_seen("h1") == (date(2024, 6, 1), "origin")

    dump = cache.dump()
    assert len(dump["content_known"]) == 1
    cache.close()


def test_swh_rejects_placeholder_token(tmp_path):
    cache = SWHCache(tmp_path / "c.sqlite")
    for bad in ["# optional; raises limit", "", "  ", "changeme", "tok with space"]:
        o = SWHRestOracle(token=bad, cache=cache)
        assert o.token is None
        assert o.graph_enabled is False
    good = SWHRestOracle(token="eyJhbGciOiJra", cache=cache)
    assert good.token == "eyJhbGciOiJra"
    assert good.graph_enabled is True
