from types import SimpleNamespace
import time
import pytest
from pipeline import fetch_news
from pipeline.errors import NewsFetchError


def _feed(*titles):
    entries = [SimpleNamespace(title=t, summary="", link="http://x",
                              published_parsed=time.gmtime()) for t in titles]
    return SimpleNamespace(entries=entries)


def test_google_news_url_encodes_query():
    url = fetch_news._google_news_feed("Cursor AI editor")
    assert "news.google.com" in url and "Cursor" in url and "when%3A14d" in url


def test_pooling_and_dedupe(monkeypatch):
    data = {"a": _feed("Same Title", "Same Title", "Unique One")}
    monkeypatch.setattr(fetch_news, "_parse_feed",
                        lambda u: data.get("a") if u == "a" else _feed())
    topic = {"key": "ai_news", "feeds": ["a"], "queries": []}
    out = fetch_news.fetch_items(topic)
    titles = [o["title"] for o in out]
    assert titles.count("Same Title") == 1 and "Unique One" in titles


def test_must_include_filters_off_topic(monkeypatch):
    monkeypatch.setattr(fetch_news, "_parse_feed",
                        lambda u: _feed("Cursor ships Composer", "OpenAI GPT-X", "DB news"))
    topic = {"key": "cursor", "must_include": ["cursor", "anysphere"],
             "feeds": ["a"], "queries": []}
    out = fetch_news.fetch_items(topic)
    assert all("cursor" in o["title"].lower() for o in out)


def test_must_include_falls_back_when_no_match(monkeypatch):
    monkeypatch.setattr(fetch_news, "_parse_feed",
                        lambda u: _feed("OpenAI news", "Google news"))
    topic = {"key": "claude", "must_include": ["claude"], "feeds": ["a"], "queries": []}
    out = fetch_news.fetch_items(topic)
    assert len(out) == 2  # fell back to full pool, never empty


def test_raises_when_completely_empty(monkeypatch):
    monkeypatch.setattr(fetch_news, "_parse_feed", lambda u: None)
    topic = {"key": "ai_news", "feeds": ["a", "b"], "queries": []}
    with pytest.raises(NewsFetchError):
        fetch_news.fetch_items(topic)
