import pytest
from pipeline import history


@pytest.fixture(autouse=True)
def _tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history.config, "HISTORY_FILE", tmp_path / "h.json")


def test_load_empty():
    assert history.load() == {"entries": []}


def test_prepend_and_recent_topics():
    h = history.load()
    history.prepend(h, {"topic": "claude", "title": "A"})
    history.prepend(h, {"topic": "cursor", "title": "B"})
    h2 = history.load()
    assert h2["entries"][0]["title"] == "B"
    assert history.recent_topics(h2, 2) == ["cursor", "claude"]


def test_update_latest():
    h = history.load()
    history.prepend(h, {"topic": "claude", "title": "A"})
    history.update_latest(h, video_id="vid123")
    assert history.load()["entries"][0]["video_id"] == "vid123"


def test_corruption_tolerant(tmp_path, monkeypatch):
    f = tmp_path / "bad.json"
    f.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(history.config, "HISTORY_FILE", f)
    assert history.load() == {"entries": []}
