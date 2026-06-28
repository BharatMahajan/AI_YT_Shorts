import json
import os
import types
from pathlib import Path

import pytest

from pipeline import analytics
from pipeline import config
from pipeline import fetch_news
from pipeline import history
from pipeline import preflight
from pipeline import render_props
from pipeline import topic_select
from pipeline import upload_youtube as up
from pipeline.errors import ConfigError, NewsFetchError, UploadError


def test_config_atomic_write_cleanup_on_replace_error(tmp_path, monkeypatch):
    p = tmp_path / "a" / "b.json"

    def _boom(src, dst):
        raise OSError("replace fail")

    monkeypatch.setattr(config.os, "replace", _boom)
    with pytest.raises(OSError):
        config.atomic_write_text(p, "{}")
    leftovers = list((tmp_path / "a").glob("*.tmp"))
    assert leftovers == []


def test_history_save_oserror_is_swallowed(monkeypatch):
    monkeypatch.setattr(history.config, "write_json", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    history.save({"entries": [{"topic": "a"}]})


def test_history_load_unexpected_shape_and_recent_topics(tmp_path, monkeypatch):
    monkeypatch.setattr(history.config, "HISTORY_FILE", tmp_path / "history.json")
    history.config.HISTORY_FILE.write_text(json.dumps({"entries": {}}), encoding="utf-8")
    assert history.load() == {"entries": []}
    assert history.recent_topics({"entries": [{"topic": "a"}, {"topic": "b"}]}, 2) == ["a", "b"]


def test_render_props_shift_hex_invalid_and_active_title_default():
    assert render_props._shift_hex("not-a-color").startswith("#")
    title, idx = render_props.active_title({"title": "A", "title_variants": ["B"]}, 5, False)
    assert title == "A" and idx == 0


def test_preflight_binary_and_run_warning(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda b: None if b in {"node", "npx", "ffmpeg"} else "/ok")
    with pytest.raises(ConfigError):
        preflight.check_binaries(require_node=True)

    monkeypatch.setattr(preflight, "check_env", lambda require_upload=True: None)
    monkeypatch.setattr(preflight, "check_binaries", lambda require_node=True: None)
    monkeypatch.setattr(preflight.config, "YT_PRIVACY", "bad")
    preflight.run(require_upload=False, require_node=False)


def test_fetch_news_helper_branches(monkeypatch):
    class E:
        media_thumbnail = [{"url": "http://img/a.png"}]
        links = []
        summary = ""

    assert fetch_news._entry_image(E()) == "http://img/a.png"

    class E2:
        links = [{"rel": "enclosure", "type": "image/png", "href": "http://img/b.png"}]
        summary = ""

    assert fetch_news._entry_image(E2()) == "http://img/b.png"

    class E3:
        links = []
        summary = '<p><img src="http://img/c.png"></p>'

    assert fetch_news._entry_image(E3()) == "http://img/c.png"

    assert fetch_news.top_image([{"image": ""}, {"image": "x"}]) == "x"
    assert fetch_news.items_to_context([]) == "No fresh items found."


def test_fetch_news_parse_feed_fail_and_date_filter(monkeypatch):
    original_download = fetch_news._download
    monkeypatch.setattr(fetch_news, "_download", lambda url: (_ for _ in ()).throw(RuntimeError("bad")))
    assert fetch_news._parse_feed("http://x") is None

    class _R:
        content = b"rss"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(fetch_news.requests, "get", lambda *a, **k: _R())
    monkeypatch.setattr(fetch_news, "_download", original_download)
    assert fetch_news._download("http://x") == b"rss"

    monkeypatch.setattr(fetch_news.feedparser, "parse", lambda raw: (_ for _ in ()).throw(RuntimeError("bad parse")))
    assert fetch_news._parse_feed("http://x") is None

    class Entry:
        def __init__(self, title, y):
            self.title = title
            self.summary = "s"
            self.link = "l"
            self.published_parsed = (y, 1, 1, 0, 0, 0, 0, 0, 0)
            self.links = []

    feed = types.SimpleNamespace(entries=[Entry("Old", 2000), Entry("New", 2030)])
    monkeypatch.setattr(fetch_news, "_parse_feed", lambda url: feed)
    out = fetch_news.fetch_items({"key": "k", "feeds": ["a"], "queries": []}, max_age_days=365)
    assert len(out) == 1 and out[0]["title"] == "New"

    monkeypatch.setattr(fetch_news, "_parse_feed", lambda url: None)
    with pytest.raises(NewsFetchError):
        fetch_news.fetch_items({"key": "k", "feeds": ["a"], "queries": []})


def test_fetch_news_misc_gaps(monkeypatch):
    class BadDateEntry:
        title = "X"
        summary = "S"
        link = "L"
        published_parsed = ("bad",)
        links = []

    class EmptyTitleEntry:
        title = ""
        summary = "S"
        link = "L"
        published_parsed = None
        links = []

    feed = types.SimpleNamespace(entries=[BadDateEntry(), EmptyTitleEntry()])
    monkeypatch.setattr(fetch_news, "_parse_feed", lambda url: feed)
    out = fetch_news.fetch_items({"key": "k", "feeds": ["a"], "queries": []}, max_age_days=3650)
    assert len(out) == 1 and out[0]["title"] == "X"
    assert fetch_news.top_image([{"image": ""}]) == ""


def test_analytics_fetch_stats_and_collect(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    payload = {
        "items": [
            {"id": "v1", "statistics": {"viewCount": "10", "likeCount": "2"}},
            {"id": "v2", "statistics": {"viewCount": "20", "likeCount": "3"}},
        ]
    }
    monkeypatch.setattr(analytics.urllib.request, "urlopen", lambda req, timeout=15: _Resp())
    monkeypatch.setattr(analytics.json, "load", lambda r: payload)
    stats = analytics._fetch_stats(["v1", "v2"])
    assert stats["v1"]["views"] == 10

    monkeypatch.setattr(analytics.config, "ENABLE_ANALYTICS", True)
    monkeypatch.setattr(analytics.config, "YT_DATA_API_KEY", "k")
    monkeypatch.setattr(analytics.config, "ANALYTICS_LOOKBACK", 10)
    hist_obj = {"entries": [{"topic": "claude", "title": "T1", "video_id": "v1"}]}
    monkeypatch.setattr(analytics.history, "load", lambda: hist_obj)
    saved = []
    monkeypatch.setattr(analytics.history, "save", lambda h: saved.append(h))
    monkeypatch.setattr(analytics, "_fetch_stats", lambda ids: {"v1": {"views": 100, "likes": 1}})
    w, hint = analytics.collect()
    assert w and "views" in hint and saved

    monkeypatch.setattr(analytics, "_fetch_stats", lambda ids: (_ for _ in ()).throw(RuntimeError("nope")))
    w2, hint2 = analytics.collect()
    assert w2 == {} and hint2 == ""

    monkeypatch.setattr(analytics.history, "load", lambda: {"entries": []})
    assert analytics.collect() == ({}, "")
    assert analytics.compute_weights([], {}) == {}


def test_topic_select_trending_and_rotate(monkeypatch):
    monkeypatch.setattr(topic_select.config, "TOPIC_STRATEGY", "rotate")
    monkeypatch.setattr(topic_select, "topic_for", lambda d=None: {"key": "ai_news"})
    assert topic_select.choose_topic() == {"key": "ai_news"}

    monkeypatch.setattr(topic_select.config, "TOPIC_STRATEGY", "trending")
    monkeypatch.setattr(topic_select.config, "TOPIC_COOLDOWN", 2)
    monkeypatch.setattr(topic_select, "TOPICS", [{"key": "a"}, {"key": "b"}])
    monkeypatch.setattr(topic_select, "topic_for", lambda d=None: {"key": "fallback"})
    monkeypatch.setattr(topic_select, "_trending_scores", lambda w: {"a": 2.0, "b": 2005.0})

    class _H:
        @staticmethod
        def load():
            return {"entries": [{"topic": "a"}]}

        @staticmethod
        def recent_topics(hist, n):
            return ["a"]

    monkeypatch.setitem(__import__("sys").modules, "pipeline.history", _H)
    out = topic_select.choose_topic(hist=None, weights={"a": 1.0})
    assert out["key"] == "b"


def test_topic_select_trending_scores_exception(monkeypatch):
    monkeypatch.setattr(topic_select, "TOPICS", [{"key": "a"}, {"key": "b"}])
    calls = {"n": 0}

    def _fetch(topic, limit=18):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("x")
        return [1, 2, 3]

    monkeypatch.setitem(__import__("sys").modules, "pipeline.fetch_news", types.SimpleNamespace(fetch_items=_fetch))
    scores = topic_select._trending_scores(weights={"b": 0.5})
    assert scores["a"] == 0
    assert scores["b"] == 3 * 1.5


def test_upload_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(up.config, "missing_env", lambda keys: ["YT_CLIENT_ID"])
    with pytest.raises(UploadError):
        up._require_credentials()

    monkeypatch.setattr(up.config, "missing_env", lambda keys: [])
    monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
    monkeypatch.setenv("YT_CLIENT_ID", "id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "sec")

    monkeypatch.setattr(up, "Credentials", lambda **kwargs: types.SimpleNamespace())
    monkeypatch.setattr(up, "build", lambda *a, **k: "svc")
    assert up._service() == "svc"

    class _Req:
        def __init__(self):
            self.c = 0

        def next_chunk(self):
            if self.c == 0:
                self.c += 1
                raise OSError("temp")
            return (None, {"id": "v1"})

    monkeypatch.setattr(up.time, "sleep", lambda *_: None)
    assert up._resumable_insert(_Req())["id"] == "v1"

    monkeypatch.setattr(up.time, "sleep", lambda *_: None)
    class _ReqAlways:
        def next_chunk(self):
            raise ConnectionError("down")

    with pytest.raises(UploadError):
        up._resumable_insert(_ReqAlways())

    monkeypatch.setattr(up.config, "VIDEO_FILE", tmp_path / "out.mp4")
    with pytest.raises(UploadError):
        up.upload({"title": "t"})

    up.config.VIDEO_FILE.write_bytes(b"video")
    monkeypatch.setattr(up.config, "REVIEW_BEFORE_PUBLISH", True)
    monkeypatch.setattr(up.config, "safe_privacy", lambda: "public")

    class _ThumbReq:
        def execute(self):
            return {}

    class _ThumbApi:
        def __init__(self, fail=False):
            self.fail = fail

        def set(self, videoId=None, media_body=None):
            if self.fail:
                raise RuntimeError("thumb fail")
            return _ThumbReq()

    class _VideosApi:
        def insert(self, part=None, body=None, media_body=None):
            return object()

    class _YT:
        def __init__(self, fail_thumb=False):
            self.fail_thumb = fail_thumb

        def videos(self):
            return _VideosApi()

        def thumbnails(self):
            return _ThumbApi(fail=self.fail_thumb)

    monkeypatch.setattr(up, "_service", lambda: _YT())
    monkeypatch.setattr(up, "_resumable_insert", lambda req: {"id": "abc"})
    monkeypatch.setattr(up, "MediaFileUpload", lambda *a, **k: object())

    thumb = tmp_path / "thumb.png"
    thumb.write_bytes(b"png")
    monkeypatch.setattr(up.config, "BUILD", tmp_path)

    assert up.upload({"title": "T", "description": "D", "tags": ["a"]}) == "abc"

    monkeypatch.setattr(up, "_service", lambda: (_ for _ in ()).throw(RuntimeError("svc fail")))
    with pytest.raises(UploadError):
        up.upload({"title": "T", "description": "D", "tags": ["a"]})

    monkeypatch.setattr(up, "_service", lambda: _YT())
    monkeypatch.setattr(up, "_resumable_insert", lambda req: (_ for _ in ()).throw(UploadError("u")))
    with pytest.raises(UploadError):
        up.upload({"title": "T", "description": "D", "tags": ["a"]})

    monkeypatch.setattr(up, "_service", lambda: _YT())
    monkeypatch.setattr(up, "_resumable_insert", lambda req: {})
    with pytest.raises(UploadError):
        up.upload({"title": "T"})

    up._set_thumbnail(_YT(fail_thumb=True), "abc")
    if thumb.exists():
        thumb.unlink()
    up._set_thumbnail(_YT(), "abc")