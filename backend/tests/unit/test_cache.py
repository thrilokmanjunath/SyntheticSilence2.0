import time

import pytest

from app.services.cache import ResultCache, make_key

CFG = {"model": "m", "mode": "pooled", "retrievers": ["wikipedia"], "rank": False, "cutoff": 2023}


def test_key_ignores_case_and_whitespace_but_not_config():
    a = make_key("Honey  never   spoils.", CFG)
    assert a == make_key("honey never spoils.", CFG)
    assert a != make_key("Honey never spoils", CFG)                       # punctuation is part of the claim
    assert a != make_key("honey never spoils.", {**CFG, "mode": "stance"})
    assert a != make_key("honey never spoils.", {**CFG, "model": "other"})


def test_roundtrip_and_hit_miss_counters():
    c = ResultCache(":memory:")
    assert c.get("k") is None
    c.set("k", {"verdict": "supported", "n": [1, 2]})
    assert c.get("k") == {"verdict": "supported", "n": [1, 2]}
    assert (c.hits, c.misses) == (1, 1)
    c.set("k", {"verdict": "refuted"})                                     # overwrite, not duplicate
    assert c.get("k") == {"verdict": "refuted"} and len(c) == 1


def test_ttl_expiry_removes_entry():
    c = ResultCache(":memory:", ttl_seconds=0)
    c.set("k", {"a": 1})
    time.sleep(0.01)
    assert c.get("k") is None
    assert len(c) == 0


def test_lru_evicts_least_recently_used():
    c = ResultCache(":memory:", max_entries=2)
    c.set("a", {"v": 1})
    time.sleep(0.01)
    c.set("b", {"v": 2})
    time.sleep(0.01)
    assert c.get("a") == {"v": 1}      # touch a, so b is now the oldest
    time.sleep(0.01)
    c.set("c", {"v": 3})
    assert c.get("b") is None
    assert c.get("a") == {"v": 1} and c.get("c") == {"v": 3}
    assert len(c) == 2


def test_persists_on_disk(tmp_path):
    path = tmp_path / "sub" / "r.sqlite3"
    first = ResultCache(path)
    first.set("k", {"v": 1})
    first.close()
    assert ResultCache(path).get("k") == {"v": 1}


def test_corrupt_value_is_a_miss(tmp_path):
    c = ResultCache(":memory:")
    c._db.execute("INSERT INTO results VALUES ('bad', 'not json', ?, ?)", (time.time(), time.time()))
    assert c.get("bad") is None
