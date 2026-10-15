import time

from recomp.verbs import trends


def test_rank_by_views_per_day_and_since():
    today = time.strftime("%Y%m%d")
    old = time.strftime("%Y%m%d", time.gmtime(time.time() - 40 * 86400))
    entries = [{"id": "a", "views": 1000, "date": old}, {"id": "b", "views": 900, "date": today},
               {"id": "c", "views": 50, "date": None}]
    ranked = trends._rank([dict(e) for e in entries], since=None)
    assert [e["id"] for e in ranked][:2] == ["b", "a"]  # 900 today beats 1000 over 40 days
    recent = trends._rank([dict(e) for e in entries], since=30)
    assert "a" not in [e["id"] for e in recent]
    assert [e["n"] for e in recent] == list(range(1, len(recent) + 1))


def test_since_parse():
    assert trends._days("7d") == 7
    assert trends._days(None) is None
