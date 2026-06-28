import os
import pytest
from pipeline import config, preflight
from pipeline.errors import ConfigError, retry, PipelineError


def test_missing_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert "GEMINI_API_KEY" in config.missing_env(["GEMINI_API_KEY"])


def test_safe_privacy(monkeypatch):
    monkeypatch.setattr(config, "YT_PRIVACY", "bogus")
    assert config.safe_privacy() == "private"
    monkeypatch.setattr(config, "YT_PRIVACY", "public")
    assert config.safe_privacy() == "public"


def test_atomic_write(tmp_path):
    p = tmp_path / "sub" / "f.json"
    config.write_json(p, {"a": 1}, indent=2)
    assert p.read_text(encoding="utf-8").strip().startswith("{")


def test_preflight_env_raises(monkeypatch):
    for k in config.REQUIRED_ENV_FOR_SCRIPT + config.REQUIRED_ENV_FOR_UPLOAD:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ConfigError):
        preflight.check_env(require_upload=True)


def test_retry_eventually_succeeds():
    calls = {"n": 0}

    @retry(exceptions=(ValueError,), tries=3, delay=0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok" and calls["n"] == 3


def test_retry_reraises_after_exhaustion():
    @retry(exceptions=(ValueError,), tries=2, delay=0)
    def always():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always()
