"""Central configuration for the daily Shorts pipeline."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path

try:  # pragma: no cover
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STATE = ROOT / "state"
BUILD.mkdir(exist_ok=True)
STATE.mkdir(exist_ok=True)

# Generated artifacts (consumed by Remotion + uploader)
AUDIO_FILE = BUILD / "voice.mp3"
CAPTIONS_FILE = BUILD / "captions.json"
SCRIPT_FILE = BUILD / "script.json"
VIDEO_FILE = BUILD / "out.mp4"
HISTORY_FILE = STATE / "history.json"

# ── Voice (US female by default; per-topic override via topic["voice"]) ──
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")
TTS_RATE = os.getenv("TTS_RATE", "+16%")
TTS_PITCH = os.getenv("TTS_PITCH", "+8Hz")
TTS_VOLUME = os.getenv("TTS_VOLUME", "+14%")
# Script language label fed to the model (e.g. "English", "Hindi", "Hinglish").
LANGUAGE = os.getenv("LANGUAGE", "English")

# ── Gemini (free tier). Tries these in order until one works. ──
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]

# ── Video target ──
WIDTH, HEIGHT, FPS = 1080, 1920, 30
TARGET_SECONDS = (50, 62)
MIN_AUDIO_SECONDS = float(os.getenv("MIN_AUDIO_SECONDS", "15"))

# ── Topic selection: "rotate" (deterministic) | "trending" (weighted by volume) ──
TOPIC_STRATEGY = os.getenv("TOPIC_STRATEGY", "rotate").lower()
# Avoid re-picking a topic used within this many recent runs (trending mode).
TOPIC_COOLDOWN = int(os.getenv("TOPIC_COOLDOWN", "2"))

# ── A/B testing of titles + thumbnails ──
AB_TESTING = os.getenv("AB_TESTING", "true").lower() == "true"
THUMB_VARIANTS = 2  # number of thumbnail layouts available

# ── Analytics loop (optional; needs YT_DATA_API_KEY for public video stats) ──
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "false").lower() == "true"
YT_DATA_API_KEY = os.getenv("YT_DATA_API_KEY", "")
ANALYTICS_LOOKBACK = int(os.getenv("ANALYTICS_LOOKBACK", "30"))  # how many past uploads

# ── Publishing ──
VALID_PRIVACY = {"public", "unlisted", "private"}
YT_PRIVACY = os.getenv("YT_PRIVACY", "public")
REVIEW_BEFORE_PUBLISH = os.getenv("REVIEW_BEFORE_PUBLISH", "false").lower() == "true"

# Credentials required for the various stages.
REQUIRED_ENV_FOR_SCRIPT = ["GEMINI_API_KEY"]
REQUIRED_ENV_FOR_UPLOAD = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]


def missing_env(keys) -> list[str]:
    return [k for k in keys if not os.environ.get(k)]


def safe_privacy() -> str:
    return YT_PRIVACY if YT_PRIVACY in VALID_PRIVACY else "private"


def atomic_write_text(path: Path, text: str) -> None:
    """Write atomically (temp file + os.replace) so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: Path, obj, indent: int | None = None) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent))
