import json
import runpy
import subprocess
import sys
from datetime import date

import pytest

from pipeline import run
from pipeline.errors import ConfigError, PipelineError, RenderError


def test_safe_scale_for_codec_behaviors():
    assert run._safe_scale_for_codec(-1, "h264") == 1.0
    assert run._safe_scale_for_codec(0.67, "vp9") == 0.67
    assert run._safe_scale_for_codec(0.74, "h264") == 0.75


def test_topic_by_key():
    assert run._topic_by_key(None) is None
    assert run._topic_by_key("does-not-exist") is None
    assert run._topic_by_key("claude")["key"] == "claude"


def test_read_json_and_stage_state(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    assert run._read_json(p) is None
    p.write_text(json.dumps({"ok": 1}), encoding="utf-8")
    assert run._read_json(p) == {"ok": 1}

    monkeypatch.setattr(run, "STAGE_STATE", tmp_path / "stage.json")
    assert run._stage_state() == {}
    (tmp_path / "stage.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    assert run._stage_state() == {}


def test_script_or_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(run.config, "SCRIPT_FILE", tmp_path / "script.json")
    with pytest.raises(PipelineError):
        run._script_or_fail()

    run.config.SCRIPT_FILE.write_text(json.dumps({"title": "x"}), encoding="utf-8")
    assert run._script_or_fail()["title"] == "x"


def test_run_script_stage_writes_outputs(monkeypatch):
    writes = []
    upd = []

    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "collect_analytics", lambda: ({"claude": 0.8}, "hint"))
    monkeypatch.setattr(run, "choose_topic", lambda **_: {"key": "claude", "title": "Claude"})
    monkeypatch.setattr(run, "fetch_items", lambda topic: [{"title": "n"}])
    monkeypatch.setattr(run, "top_image", lambda items: "img.png")
    monkeypatch.setattr(run, "generate", lambda *_, **__: {"title": "T", "narration": "n"})
    monkeypatch.setattr(run, "active_title", lambda script, ordinal, ab: ("Picked", 1))
    monkeypatch.setattr(run.history, "load", lambda: {"entries": []})
    monkeypatch.setattr(run.history, "update_latest", lambda *a, **k: upd.append(k))
    monkeypatch.setattr(run.config, "write_json", lambda path, obj, indent=None: writes.append((path, obj, indent)))

    class _D:
        @staticmethod
        def today():
            return date(2026, 6, 28)

    monkeypatch.setattr(run, "date", _D)
    monkeypatch.setattr(run.config, "AB_TESTING", True)
    monkeypatch.setattr(run.config, "THUMB_VARIANTS", 2)

    run.run_script_stage()

    assert len(writes) == 2
    assert writes[0][1]["title"] == "Picked"
    assert writes[1][1]["topic_key"] == "claude"
    assert upd and upd[0]["active_title"] == "Picked"


def test_run_voice_stage_missing_context_raises(monkeypatch):
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"topic": "missing", "narration": "n"})
    monkeypatch.setattr(run, "_stage_state", lambda: {})
    with pytest.raises(PipelineError):
        run.run_voice_stage()


def test_run_voice_stage_short_audio_raises(monkeypatch):
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"topic": "claude", "narration": "n", "title": "t"})
    monkeypatch.setattr(run, "_stage_state", lambda: {"topic_key": "claude", "thumb_variant": 1})
    monkeypatch.setattr(run, "synthesize", lambda *_args, **_kw: {"duration": 1.0, "words": []})
    monkeypatch.setattr(run.config, "MIN_AUDIO_SECONDS", 15.0)
    with pytest.raises(PipelineError):
        run.run_voice_stage()


def test_run_voice_stage_success(monkeypatch):
    writes = []
    thumbs = []
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"topic": "claude", "narration": "hello", "title": "T", "topic_title": "TT"})
    monkeypatch.setattr(run, "_stage_state", lambda: {"topic_key": "claude", "hero_image": "h.png", "thumb_variant": 1})
    monkeypatch.setattr(run, "synthesize", lambda *_args, **_kw: {"duration": 55.0, "words": []})
    monkeypatch.setattr(run, "build_props", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(run, "make_thumb", lambda script, variant=0: thumbs.append((script, variant)))
    monkeypatch.setattr(run.config, "write_json", lambda path, obj, indent=None: writes.append((path, obj)))
    monkeypatch.setattr(run.config, "TARGET_SECONDS", (50, 62))
    run.run_voice_stage()
    assert writes and writes[0][1] == {"ok": True}
    assert thumbs and thumbs[0][1] == 1


def test_run_voice_stage_thumb_variant_default(monkeypatch):
    writes = []
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"topic": "claude", "narration": "hello", "title": "T", "topic_title": "TT"})
    monkeypatch.setattr(run, "_stage_state", lambda: {"topic_key": "claude", "hero_image": "h.png"})
    monkeypatch.setattr(run, "synthesize", lambda *_args, **_kw: {"duration": 55.0, "words": []})
    monkeypatch.setattr(run, "build_props", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(run, "make_thumb", lambda *a, **k: None)
    monkeypatch.setattr(run.config, "write_json", lambda path, obj, indent=None: writes.append((path, obj)))
    monkeypatch.setattr(run.config, "TARGET_SECONDS", (50, 62))
    monkeypatch.setattr(run.config, "AB_TESTING", False)
    run.run_voice_stage()
    assert writes


def test_run_voice_stage_outside_ideal_window_warns(monkeypatch):
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"topic": "claude", "narration": "hello", "title": "T", "topic_title": "TT"})
    monkeypatch.setattr(run, "_stage_state", lambda: {"topic_key": "claude", "hero_image": "h.png", "thumb_variant": 0})
    monkeypatch.setattr(run, "synthesize", lambda *_args, **_kw: {"duration": 90.0, "words": []})
    monkeypatch.setattr(run, "build_props", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(run, "make_thumb", lambda *a, **k: None)
    monkeypatch.setattr(run.config, "write_json", lambda *a, **k: None)
    monkeypatch.setattr(run.config, "TARGET_SECONDS", (50, 62))
    run.run_voice_stage()


def test_run_render_stage_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "RENDER_PROPS", tmp_path / "missing.json")
    with pytest.raises(RenderError):
        run.run_render_stage()

    props = tmp_path / "render-props.json"
    props.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run, "RENDER_PROPS", props)
    monkeypatch.setattr(run.config, "AUDIO_FILE", tmp_path / "missing.mp3")
    with pytest.raises(RenderError):
        run.run_render_stage()

    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"x")
    monkeypatch.setattr(run.config, "AUDIO_FILE", audio)
    called = []
    monkeypatch.setattr(run, "render_video", lambda: called.append(True))
    monkeypatch.setattr(run.config, "VIDEO_FILE", tmp_path / "out.mp4")
    run.run_render_stage()
    assert called


def test_run_upload_stage(monkeypatch):
    monkeypatch.setattr(run.preflight, "run", lambda **_: None)
    monkeypatch.setattr(run, "_script_or_fail", lambda: {"title": "x"})
    monkeypatch.setattr(run.history, "load", lambda: {"entries": [{}]})
    updates = []
    monkeypatch.setattr(run.history, "update_latest", lambda *a, **k: updates.append(k))

    fake_mod = type("M", (), {"upload": staticmethod(lambda script: "vid1")})
    monkeypatch.setitem(sys.modules, "pipeline.upload_youtube", fake_mod)
    run.run_upload_stage()
    assert updates and updates[0]["video_id"] == "vid1"


def test_render_video_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "REMOTION_DIR", tmp_path / "missing")
    with pytest.raises(RenderError):
        run.render_video()

    remotion = tmp_path / "remotion"
    public = remotion / "public"
    public.mkdir(parents=True)
    props = tmp_path / "props.json"
    props.write_text("{}", encoding="utf-8")
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"abc")
    video = tmp_path / "out.mp4"
    monkeypatch.setattr(run, "REMOTION_DIR", remotion)
    monkeypatch.setattr(run, "RENDER_PROPS", props)
    monkeypatch.setattr(run.config, "AUDIO_FILE", audio)
    monkeypatch.setattr(run.config, "VIDEO_FILE", video)

    def _cp(*_a, **_k):
        raise subprocess.CalledProcessError(returncode=2, cmd="x")

    monkeypatch.setattr(run.subprocess, "run", _cp)
    with pytest.raises(RenderError):
        run.render_video()

    monkeypatch.setattr(run.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("npx")))
    with pytest.raises(RenderError):
        run.render_video()

    monkeypatch.setattr(run.subprocess, "run", lambda *_a, **_k: None)
    if video.exists():
        video.unlink()
    with pytest.raises(RenderError):
        run.render_video()

    video.write_bytes(b"ok")
    run.render_video()
    assert (public / "voice.mp3").exists()


def test_render_video_scale_adjust_branch(tmp_path, monkeypatch):
    remotion = tmp_path / "remotion"
    public = remotion / "public"
    public.mkdir(parents=True)
    props = tmp_path / "props.json"
    props.write_text("{}", encoding="utf-8")
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"abc")
    video = tmp_path / "out.mp4"
    video.write_bytes(b"ok")

    monkeypatch.setattr(run, "REMOTION_DIR", remotion)
    monkeypatch.setattr(run, "RENDER_PROPS", props)
    monkeypatch.setattr(run.config, "AUDIO_FILE", audio)
    monkeypatch.setattr(run.config, "VIDEO_FILE", video)
    monkeypatch.setenv("REMOTION_SCALE", "0.74")
    monkeypatch.setenv("REMOTION_CODEC", "h264")
    monkeypatch.setattr(run.subprocess, "run", lambda *_a, **_k: None)
    run.render_video()


def test_pipeline_control_flow(monkeypatch):
    calls = []
    monkeypatch.setattr(run, "run_script_stage", lambda: calls.append("s"))
    monkeypatch.setattr(run, "run_voice_stage", lambda: calls.append("v"))
    monkeypatch.setattr(run, "run_render_stage", lambda: calls.append("r"))
    monkeypatch.setattr(run, "run_upload_stage", lambda: calls.append("u"))

    class Args:
        def __init__(self, no_render=False, no_upload=False):
            self.no_render = no_render
            self.no_upload = no_upload

    run._pipeline(Args(no_render=True))
    assert calls == ["s", "v"]
    calls.clear()
    run._pipeline(Args(no_upload=True))
    assert calls == ["s", "v", "r"]
    calls.clear()
    run._pipeline(Args())
    assert calls == ["s", "v", "r", "u"]


def test_main_dispatch_and_error_paths(monkeypatch):
    monkeypatch.setattr(run, "_pipeline", lambda args: None)
    assert run.main(["--stage", "all"]) == 0

    for stage_name, fn_name in [
        ("script", "run_script_stage"),
        ("voice", "run_voice_stage"),
        ("render", "run_render_stage"),
        ("upload", "run_upload_stage"),
    ]:
        called = []
        monkeypatch.setattr(run, fn_name, lambda: called.append(stage_name))
        assert run.main(["--stage", stage_name]) == 0
        assert called == [stage_name]

    noted = []
    monkeypatch.setattr(run, "notify_failure", lambda summary, detail="": noted.append((summary, detail)))
    monkeypatch.setattr(run, "run_script_stage", lambda: (_ for _ in ()).throw(ConfigError("bad cfg")))
    assert run.main(["--stage", "script"]) == 2

    monkeypatch.setattr(run, "run_script_stage", lambda: (_ for _ in ()).throw(PipelineError("bad run")))
    assert run.main(["--stage", "script"]) == 1

    monkeypatch.setattr(run, "run_script_stage", lambda: (_ for _ in ()).throw(RuntimeError("oops")))
    assert run.main(["--stage", "script"]) == 1
    assert len(noted) >= 3


def test_run_module_main_block_executes(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "")
    monkeypatch.setattr(sys, "argv", ["pipeline.run", "--stage", "script"])
    with pytest.raises(SystemExit):
        runpy.run_module("pipeline.run", run_name="__main__")