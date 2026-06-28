"""Topic selection strategies.

  - "rotate"   : deterministic daily rotation (default, zero extra network).
  - "trending" : pick the topic with the most fresh items right now, while
                 avoiding topics used in the last few runs (cooldown), and
                 optionally biased by past performance weights (analytics loop).
"""
from __future__ import annotations
from datetime import date

from . import config
from .logging_setup import get_logger
from .topics import TOPICS, topic_for

log = get_logger(__name__)


def pick_by_scores(scores: dict[str, float], recent: list[str],
                   cooldown: int) -> str:
    """Pure: choose the highest-scoring topic key, penalizing recent picks.

    A topic used within the last `cooldown` runs gets a heavy penalty so we keep
    variety; if every topic is penalized we still return the best raw score.
    """
    penalized = set(recent[:cooldown])
    best_key, best_val = None, float("-inf")
    for key, raw in scores.items():
        val = raw - (1000 if key in penalized else 0)
        if val > best_val:
            best_key, best_val = key, val
    return best_key or next(iter(scores))


def _trending_scores(weights: dict[str, float] | None) -> dict[str, float]:
    """Count fresh items per topic (cheap proxy for 'what's happening')."""
    from .fetch_news import fetch_items  # local import keeps this module light
    weights = weights or {}
    scores: dict[str, float] = {}
    for t in TOPICS:
        try:
            n = len(fetch_items(t, limit=18))
        except Exception as e:  # NewsFetchError or network
            log.warning("Trending count failed for '%s' (%s); scoring 0.", t["key"], e)
            n = 0
        scores[t["key"]] = n * (1.0 + weights.get(t["key"], 0.0))
        log.info("Trending score for '%s': %.1f (items=%d).", t["key"], scores[t["key"]], n)
    return scores


def choose_topic(hist: dict | None = None,
                 weights: dict[str, float] | None = None,
                 d: date | None = None) -> dict:
    """Return the topic dict to use today, per config.TOPIC_STRATEGY."""
    if config.TOPIC_STRATEGY != "trending":
        return topic_for(d)

    from . import history
    hist = hist if hist is not None else history.load()
    recent = history.recent_topics(hist, config.TOPIC_COOLDOWN)
    scores = _trending_scores(weights)
    key = pick_by_scores(scores, recent, config.TOPIC_COOLDOWN)
    chosen = next((t for t in TOPICS if t["key"] == key), None) or topic_for(d)
    log.info("Topic strategy=trending → chose '%s'.", chosen["key"])
    return chosen
