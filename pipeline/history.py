"""Centralized, corruption-tolerant access to state/history.json.

Each entry records what was made (for anti-repetition) and, after upload, how it
performed (for the analytics loop). Schema (all optional except topic/title):

    {
      "topic": "claude", "title": "...", "hook_style": "...",
      "title_variants": ["...", "..."], "thumb_variant": 0,
      "video_id": "abc123", "published_at": "2026-06-27T03:31:00+00:00",
      "stats": {"views": 0, "likes": 0, "fetched_at": "..."}
    }
"""
from __future__ import annotations
import json

from . import config
from .logging_setup import get_logger

log = get_logger(__name__)

MAX_ENTRIES = 200


def load() -> dict:
    if not config.HISTORY_FILE.exists():
        return {"entries": []}
    try:
        data = json.loads(config.HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
        log.warning("history.json has unexpected shape; resetting.")
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Could not read history.json (%s); starting fresh.", e)
    return {"entries": []}


def save(hist: dict) -> None:
    hist["entries"] = hist.get("entries", [])[:MAX_ENTRIES]
    try:
        config.write_json(config.HISTORY_FILE, hist, indent=2)
    except OSError as e:  # pragma: no cover
        log.warning("Could not persist history.json (%s).", e)


def prepend(hist: dict, entry: dict) -> dict:
    hist["entries"] = ([entry] + hist.get("entries", []))[:MAX_ENTRIES]
    save(hist)
    return hist


def update_latest(hist: dict, **fields) -> dict:
    """Merge `fields` into the most recent entry (e.g. video_id after upload)."""
    if hist.get("entries"):
        hist["entries"][0].update(fields)
        save(hist)
    return hist


def recent_titles(hist: dict, key: str, n: int = 8) -> list[dict]:
    return [e for e in hist.get("entries", []) if e.get("topic") == key][:n]


def recent_topics(hist: dict, n: int) -> list[str]:
    return [e.get("topic") for e in hist.get("entries", [])[:n] if e.get("topic")]
