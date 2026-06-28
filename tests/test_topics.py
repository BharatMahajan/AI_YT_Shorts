from datetime import date
from pipeline import topics


def test_rotation_cycles_through_all_four():
    keys = {topics.topic_for(date.fromordinal(d))["key"]
            for d in range(1000, 1004)}
    assert keys == {"ai_news", "copilot", "claude", "cursor"}


def test_consecutive_days_differ():
    a = topics.topic_for(date.fromordinal(5000))["key"]
    b = topics.topic_for(date.fromordinal(5001))["key"]
    assert a != b


def test_every_topic_has_required_fields():
    for t in topics.TOPICS:
        assert t["key"] and t["title"] and t["accent"].startswith("#")
        assert len(t["feeds"]) >= 2 and len(t["queries"]) >= 2


def test_narrow_topics_have_must_include():
    for key in ("copilot", "claude", "cursor"):
        t = next(x for x in topics.TOPICS if x["key"] == key)
        assert t.get("must_include")
