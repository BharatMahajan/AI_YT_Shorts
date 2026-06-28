import sys
import types

import pytest

from pipeline import generate_script as gs
from pipeline.errors import ScriptGenerationError


def test_generate_with_fallback_rate_limit_then_success(monkeypatch):
    calls = {"n": 0}

    class _Models:
        def generate_content(self, model, contents):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("429 rate limit")
            return types.SimpleNamespace(text='{"title":"t","lines":["a"]}')

    client = types.SimpleNamespace(models=_Models())
    monkeypatch.setattr(gs.time, "sleep", lambda *_: None)
    out = gs._generate_with_fallback(client, "p")
    assert out.text


def test_generate_with_fallback_limit_zero_tries_next(monkeypatch):
    attempts = []

    class _Models:
        def generate_content(self, model, contents):
            attempts.append(model)
            if len(attempts) == 1:
                raise RuntimeError("RESOURCE_EXHAUSTED limit: 0")
            return types.SimpleNamespace(text='{"title":"t","lines":["a"]}')

    monkeypatch.setattr(gs.config, "GEMINI_MODEL", "m1")
    monkeypatch.setattr(gs.config, "GEMINI_FALLBACK_MODELS", ["m2"])
    out = gs._generate_with_fallback(types.SimpleNamespace(models=_Models()), "p")
    assert out.text and attempts == ["m1", "m2"]


def test_generate_with_fallback_all_fail_raises(monkeypatch):
    class _Models:
        def generate_content(self, model, contents):
            raise RuntimeError("hard fail")

    monkeypatch.setattr(gs.config, "GEMINI_MODEL", "m1")
    monkeypatch.setattr(gs.config, "GEMINI_FALLBACK_MODELS", ["m2"])
    with pytest.raises(ScriptGenerationError):
        gs._generate_with_fallback(types.SimpleNamespace(models=_Models()), "p")


def test_recent_summary_and_compute_empty_case():
    assert gs._recent_summary({"entries": []}, "claude") == "None yet."
    txt = gs._recent_summary(
        {"entries": [{"topic": "claude", "title": "A", "hook_style": "H"}]},
        "claude",
    )
    assert "A" in txt


def test_build_prompt_contains_perf_hint(monkeypatch):
    monkeypatch.setattr(gs.config, "LANGUAGE", "English")
    p = gs._build_prompt(
        {"title": "Topic", "focus": "Focus"},
        [{"title": "N", "summary": "S", "link": "L", "published": None}],
        "hook",
        "avoid",
        "- past",
    )
    assert "WHAT HAS PERFORMED WELL RECENTLY" in p


def test_extract_json_unparseable_object_and_no_object_errors():
    with pytest.raises(ScriptGenerationError):
        gs._extract_json("not-json {oops}")
    with pytest.raises(ScriptGenerationError):
        gs._extract_json("plain prose only")


def test_validate_non_dict_raises():
    with pytest.raises(ScriptGenerationError):
        gs._validate("bad")


def test_normalize_points_string_path():
    topic = {"key": "claude", "title": "Claude", "accent": "#111"}
    out = gs._normalize({"title": "T", "lines": ["a"], "points": ["First"]}, topic, "hook")
    assert out["points"][0]["heading"] == "First"


def test_generate_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ScriptGenerationError):
        gs.generate({"key": "claude"}, [])


def test_generate_success_and_import_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Client:
        def __init__(self, api_key):
            self.models = object()

    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=types.SimpleNamespace(Client=_Client)))
    monkeypatch.setattr(gs, "_generate_with_fallback", lambda client, prompt: types.SimpleNamespace(text='{"title":"T","lines":["a"],"title_variants":["A"]}'))
    monkeypatch.setattr(gs.history, "load", lambda: {"entries": []})
    prepended = []
    monkeypatch.setattr(gs.history, "prepend", lambda hist, e: prepended.append(e))
    writes = []
    monkeypatch.setattr(gs.config, "write_json", lambda p, o, indent=None: writes.append(o))
    monkeypatch.setattr(gs.random, "choice", lambda arr: arr[0])

    topic = {"key": "claude", "title": "Claude", "accent": "#000", "focus": "f"}
    out = gs.generate(topic, [{"title": "N", "summary": "S", "link": "L", "published": None}], perf_hint="")
    assert out["title"] == "T" and prepended and writes

    # ImportError path.
    monkeypatch.setitem(sys.modules, "google", None)
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google":
            raise ImportError("no google")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(ScriptGenerationError):
        gs.generate(topic, [])
