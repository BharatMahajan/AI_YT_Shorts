from pipeline import analytics

ENTRIES = [
    {"topic": "claude", "title": "C1", "video_id": "v1"},
    {"topic": "claude", "title": "C2", "video_id": "v2"},
    {"topic": "cursor", "title": "U1", "video_id": "v3"},
    {"topic": "ai_news", "title": "N1", "video_id": "v4"},  # no stats
]
STATS = {
    "v1": {"views": 100, "likes": 5},
    "v2": {"views": 300, "likes": 9},
    "v3": {"views": 50, "likes": 1},
}


def test_compute_weights_normalized():
    w = analytics.compute_weights(ENTRIES, STATS)
    # claude avg = 200, cursor = 50 → claude is the max (1.0)
    assert w["claude"] == 1.0
    assert 0 < w["cursor"] < 1.0
    assert "ai_news" not in w  # had no stats


def test_perf_hint_orders_by_views():
    hint = analytics.perf_hint(ENTRIES, STATS)
    assert hint.splitlines()[0].startswith("- C2")  # 300 views first


def test_collect_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(analytics.config, "ENABLE_ANALYTICS", False)
    assert analytics.collect() == ({}, "")
