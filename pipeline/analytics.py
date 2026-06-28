"""Optional analytics loop.

Pulls public view stats for past uploads and turns them into:
  (a) per-topic weights for trending topic selection, and
  (b) a short "what worked" hint injected into the script prompt.

Uses the YouTube Data API with a simple API key (YT_DATA_API_KEY) to read
*public* video statistics — no extra OAuth scope required. Fully optional:
returns no-ops unless ENABLE_ANALYTICS=true and a key is configured.
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request

from . import config, history
from .logging_setup import get_logger

log = get_logger(__name__)


def _fetch_stats(video_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):  # API allows 50 ids per call
        batch = video_ids[i:i + 50]
        params = urllib.parse.urlencode({
            "part": "statistics", "id": ",".join(batch), "key": config.YT_DATA_API_KEY,
        })
        url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "ai-shorts-bot"})
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            data = json.load(r)
        for item in data.get("items", []):
            st = item.get("statistics", {})
            out[item["id"]] = {
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
            }
    return out


def compute_weights(entries: list[dict], stats: dict[str, dict]) -> dict[str, float]:
    """Pure: average views per topic, normalized to 0..1."""
    by_topic: dict[str, list[int]] = {}
    for e in entries:
        s = stats.get(e.get("video_id", ""))
        if s:
            by_topic.setdefault(e["topic"], []).append(s["views"])
    if not by_topic:
        return {}
    avg = {k: sum(v) / len(v) for k, v in by_topic.items()}
    mx = max(avg.values()) or 1.0
    return {k: v / mx for k, v in avg.items()}


def perf_hint(entries: list[dict], stats: dict[str, dict], top_n: int = 3) -> str:
    """Pure: a short bullet list of the best-performing past titles."""
    scored = [(stats[e["video_id"]]["views"], e.get("title", ""), e.get("topic", ""))
              for e in entries if e.get("video_id") in stats]
    scored.sort(reverse=True)
    return "\n".join(f"- {t} ({v} views, topic: {tp})" for v, t, tp in scored[:top_n])


def collect() -> tuple[dict[str, float], str]:
    """Return (weights, perf_hint). Safe no-op if disabled/unconfigured."""
    if not config.ENABLE_ANALYTICS or not config.YT_DATA_API_KEY:
        return {}, ""
    hist = history.load()
    entries = [e for e in hist.get("entries", []) if e.get("video_id")][:config.ANALYTICS_LOOKBACK]
    if not entries:
        return {}, ""
    try:
        stats = _fetch_stats([e["video_id"] for e in entries])
    except Exception as e:  # pragma: no cover - network
        log.warning("Analytics fetch failed (%s); skipping.", e)
        return {}, ""

    for e in entries:  # write stats back for auditing
        if e["video_id"] in stats:
            e["stats"] = stats[e["video_id"]]
    history.save(hist)

    weights = compute_weights(entries, stats)
    hint = perf_hint(entries, stats)
    if weights:
        log.info("Analytics topic weights: %s", {k: round(v, 2) for k, v in weights.items()})
    return weights, hint
