import asyncio
import runpy
import types

import pytest

from pipeline import healthcheck as hc
from pipeline import notify
from pipeline import tts
from pipeline.errors import ConfigError, TTSError


def test_notify_post_uses_urlopen(monkeypatch):
    class _Resp:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=15: _Resp())
    status = notify._post("https://x", {"a": 1}, {"Content-Type": "application/json"})
    assert status == 204


def test_notify_failure_paths(monkeypatch):
    logs = []
    monkeypatch.setattr(notify.log, "info", lambda *a, **k: logs.append(("info", a)))
    monkeypatch.setattr(notify.log, "warning", lambda *a, **k: logs.append(("warn", a)))

    calls = []
    monkeypatch.setattr(notify, "_post", lambda *a, **k: calls.append(a) or 200)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://slack")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    notify.notify_failure("sum", "detail")
    assert calls

    def _raise(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(notify, "_post", _raise)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    notify.notify_failure("sum2", "detail2")
    assert any(level == "warn" for level, _ in logs)

    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    notify.notify_failure("sum3", "")
    assert any("No notification channel configured" in " ".join(map(str, args)) for level, args in logs if level == "info")


def test_notify_github_success(monkeypatch):
    calls = []
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setattr(notify, "_post", lambda *a, **k: calls.append(a) or 201)
    notify.notify_failure("sum", "detail")
    assert calls and "api.github.com" in calls[0][0]


def test_healthcheck_youtube_missing(monkeypatch):
    monkeypatch.setattr(hc.config, "missing_env", lambda keys: ["YT_CLIENT_ID"])
    with pytest.raises(ConfigError):
        hc.check_youtube_token()


def test_healthcheck_youtube_and_gemini_success(monkeypatch):
    monkeypatch.setattr(hc.config, "missing_env", lambda keys: [])
    monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
    monkeypatch.setenv("YT_CLIENT_ID", "id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    class _Creds:
        def __init__(self, **kwargs):
            self.token = None

        def refresh(self, req):
            self.token = "ok"

    class _Request:
        pass

    monkeypatch.setitem(__import__("sys").modules, "google.oauth2.credentials", types.SimpleNamespace(Credentials=_Creds))
    monkeypatch.setitem(__import__("sys").modules, "google.auth.transport.requests", types.SimpleNamespace(Request=_Request))

    class _Models:
        def list(self):
            return iter([{"id": "m"}])

    class _Client:
        def __init__(self, api_key):
            self.models = _Models()

    monkeypatch.setitem(__import__("sys").modules, "google", types.SimpleNamespace(genai=types.SimpleNamespace(Client=_Client)))

    hc.check_youtube_token()
    hc.check_gemini()


def test_healthcheck_youtube_refresh_without_token_raises(monkeypatch):
    monkeypatch.setattr(hc.config, "missing_env", lambda keys: [])
    monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
    monkeypatch.setenv("YT_CLIENT_ID", "id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "sec")

    class _Creds:
        def __init__(self, **kwargs):
            self.token = None

        def refresh(self, req):
            self.token = None

    class _Request:
        pass

    monkeypatch.setitem(__import__("sys").modules, "google.oauth2.credentials", types.SimpleNamespace(Credentials=_Creds))
    monkeypatch.setitem(__import__("sys").modules, "google.auth.transport.requests", types.SimpleNamespace(Request=_Request))
    with pytest.raises(ConfigError):
        hc.check_youtube_token()


def test_healthcheck_main_paths(monkeypatch):
    noted = []
    monkeypatch.setattr(hc, "notify_failure", lambda summary, detail: noted.append((summary, detail)))

    monkeypatch.setattr(hc, "check_youtube_token", lambda: None)
    monkeypatch.setattr(hc, "check_gemini", lambda: None)
    assert hc.main([]) == 0

    monkeypatch.setattr(hc, "check_youtube_token", lambda: (_ for _ in ()).throw(RuntimeError("yt bad")))
    monkeypatch.setattr(hc, "check_gemini", lambda: (_ for _ in ()).throw(RuntimeError("gem bad")))
    assert hc.main([]) == 1
    assert noted


def test_healthcheck_check_gemini_missing_key(monkeypatch):
    monkeypatch.setattr(hc.config, "missing_env", lambda keys: ["GEMINI_API_KEY"])
    with pytest.raises(ConfigError):
        hc.check_gemini()


def test_healthcheck_module_main_block(monkeypatch):
    monkeypatch.setattr(__import__("sys"), "argv", ["pipeline.healthcheck"])
    with pytest.raises(SystemExit):
        runpy.run_module("pipeline.healthcheck", run_name="__main__")


class _FakeCommunicate:
    def __init__(self, text, voice, rate, pitch, volume):
        self.events = [
            {"type": "audio", "data": b"abc"},
            {"type": "WordBoundary", "text": "Hi", "offset": 0, "duration": 10_000_000},
        ]

    async def stream(self):
        for e in self.events:
            yield e


class _NoAudioCommunicate:
    def __init__(self, text, voice, rate, pitch, volume):
        self.events = [{"type": "WordBoundary", "text": "Hi", "offset": 0, "duration": 10_000_000}]

    async def stream(self):
        for e in self.events:
            yield e


def test_tts_synthesize_async_and_run(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.config, "AUDIO_FILE", tmp_path / "voice.mp3")
    monkeypatch.setattr(tts.edge_tts, "Communicate", _FakeCommunicate)
    words = asyncio.run(tts._synthesize_async("hello", "en-US-JennyNeural"))
    assert words and tts.config.AUDIO_FILE.exists()

    monkeypatch.setattr(tts, "_synthesize_async", lambda text, voice: [{"text": "x", "start": 0, "end": 1}])
    monkeypatch.setattr(tts.asyncio, "run", lambda coro: [{"text": "x", "start": 0, "end": 1}])
    assert tts._run_synthesis("h", "v")[0]["text"] == "x"


def test_tts_synthesize_async_no_audio_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.config, "AUDIO_FILE", tmp_path / "voice.mp3")
    monkeypatch.setattr(tts.edge_tts, "Communicate", _NoAudioCommunicate)
    with pytest.raises(TTSError):
        asyncio.run(tts._synthesize_async("hello", "en-US-JennyNeural"))


def test_tts_audio_length_and_synthesize_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.config, "AUDIO_FILE", tmp_path / "voice.mp3")
    monkeypatch.setattr(tts.config, "CAPTIONS_FILE", tmp_path / "captions.json")
    tts.config.AUDIO_FILE.write_bytes(b"abc")

    class _Info:
        length = 12.5

    class _M:
        def __init__(self, path):
            self.info = _Info()

    monkeypatch.setitem(__import__("sys").modules, "mutagen.mp3", types.SimpleNamespace(MP3=_M))
    assert tts._audio_length_seconds() == 12.5

    monkeypatch.setitem(__import__("sys").modules, "mutagen.mp3", types.SimpleNamespace(MP3=lambda p: (_ for _ in ()).throw(RuntimeError("bad"))))
    assert tts._audio_length_seconds() == 0.0

    monkeypatch.setattr(tts, "_run_synthesis", lambda text, voice: [{"text": "a", "start": 0.0, "end": 2.0}])
    monkeypatch.setattr(tts, "_audio_length_seconds", lambda: 10.0)
    wrote = []
    monkeypatch.setattr(tts.config, "write_json", lambda path, obj: wrote.append((path, obj)))
    out = tts.synthesize("hello", voice="v")
    assert out["duration"] == 10.0 and wrote

    monkeypatch.setattr(tts, "_audio_length_seconds", lambda: 0.0)
    out2 = tts.synthesize("hello", voice="v")
    assert out2["duration"] == 2.0

    monkeypatch.setattr(tts, "_run_synthesis", lambda text, voice: [])
    with pytest.raises(TTSError):
        tts.synthesize("hello", voice="v")

    # Empty/missing audio file branch.
    if tts.config.AUDIO_FILE.exists():
        tts.config.AUDIO_FILE.unlink()
    monkeypatch.setattr(tts, "_run_synthesis", lambda text, voice: [{"text": "a", "start": 0.0, "end": 1.0}])
    with pytest.raises(TTSError):
        tts.synthesize("hello", voice="v")

    with pytest.raises(TTSError):
        tts.synthesize("   ", voice="v")