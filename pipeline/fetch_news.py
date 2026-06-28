"""Pull the freshest items for a topic from RSS feeds + Google News (all free).

Production notes:
  * every network read has a timeout and a User-Agent (avoids hangs / 403s)
  * individual feed failures are isolated and logged, never fatal
  * a best-effort image URL is captured per item for the optional hero visual
  * if no usable items survive, we raise NewsFetchError so the run aborts cleanly
"""
from __future__ import annotations
import re
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser
import requests

from .errors import NewsFetchError, retry
from .logging_setup import get_logger

log = get_logger(__name__)

_UA = "Mozilla/5.0 (compatible; AI-Shorts-Bot/1.0; +https://github.com/)"
_TIMEOUT = 12


def _google_news_feed(query: str, when: str = "14d") -> str:
    q = urllib.parse.quote(f"{query} when:{when}")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _entry_image(e) -> str:
    """Best-effort hero image URL from a feed entry (media tags / enclosure / <img>)."""
    media = getattr(e, "media_thumbnail", None) or getattr(e, "media_content", None)
    if media:
        url = media[0].get("url")
        if url:
            return url
    for link in getattr(e, "links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(e, "summary", "") or "")
    return m.group(1) if m else ""


@retry(exceptions=(requests.RequestException,), tries=2, delay=1.5)
def _download(url: str) -> bytes:
    resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": _UA})
    resp.raise_for_status()
    return resp.content


def _parse_feed(url: str):
    try:
        raw = _download(url)
    except Exception as exc:
        log.debug("feed download failed (%s): %s", url, exc)
        return None
    try:
        return feedparser.parse(raw)
    except Exception as exc:  # pragma: no cover
        log.debug("feed parse failed (%s): %s", url, exc)
        return None


def fetch_items(topic: dict, limit: int = 18, per_feed: int = 5,
                max_age_days: int = 30) -> list[dict]:
    """Return a rich, de-duped, on-topic pool of recent items, newest first."""
    items: list[dict] = []
    urls = list(topic.get("feeds", []))
    queries = topic.get("queries") or ([topic["query"]] if topic.get("query") else [])
    urls += [_google_news_feed(q) for q in queries]

    ok_feeds = 0
    for url in urls:
        feed = _parse_feed(url)
        if feed is None or not getattr(feed, "entries", None):
            continue
        ok_feeds += 1
        for e in feed.entries[:per_feed]:
            published = None
            if getattr(e, "published_parsed", None):
                try:
                    published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    published = None
            title = _clean(getattr(e, "title", ""))
            if not title:
                continue
            items.append({
                "title": title,
                "summary": _clean(getattr(e, "summary", ""))[:600],
                "link": getattr(e, "link", ""),
                "image": _entry_image(e),
                "published": published,
            })

    log.info("Fetched %d raw items from %d/%d reachable sources for topic '%s'.",
             len(items), ok_feeds, len(urls), topic.get("key", "?"))

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    items = [it for it in items if it["published"] is None or it["published"] >= cutoff]
    items.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)

    seen, out = set(), []
    for it in items:
        k = it["title"].lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it)

    inc = [k.lower() for k in (topic.get("must_include") or [])]
    if inc:
        on_topic = [it for it in out
                    if any(k in (it["title"] + " " + it["summary"]).lower() for k in inc)]
        if on_topic:
            out = on_topic
        else:
            log.warning("No items matched must_include=%s for '%s'; using full pool.",
                        inc, topic.get("key", "?"))

    out = out[:limit]
    if not out:
        raise NewsFetchError(
            f"No usable news items for topic '{topic.get('key', '?')}'. "
            "All feeds were unreachable/empty and Google News returned nothing."
        )
    log.info("Returning %d candidate items for the script.", len(out))
    return out


def top_image(items: list[dict]) -> str:
    """First available hero image across the candidate items ('' if none)."""
    for it in items:
        if it.get("image"):
            return it["image"]
    return ""


def items_to_context(items: list[dict]) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        d = it["published"].strftime("%Y-%m-%d") if it["published"] else "recent"
        lines.append(f"{i}. [{d}] {it['title']} — {it['summary']} (source: {it['link']})")
    return "\n".join(lines) if lines else "No fresh items found."
