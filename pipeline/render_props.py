"""Build the typed props object Remotion consumes (build/render-props.json).

Pure and side-effect-free so it is easy to unit-test. Adds the richer-visuals
fields (pattern, secondary accent, hero image) and the A/B selection (active
title + thumbnail variant).
"""
from __future__ import annotations


def _shift_hex(hex_color: str, amount: int = 40) -> str:
    """Lighten/rotate a hex color a touch for a 2-tone gradient (deterministic)."""
    try:
        n = int(hex_color.replace("#", ""), 16)
        r, g, b = (n >> 16) & 255, (n >> 8) & 255, n & 255
    except (ValueError, AttributeError):
        r, g, b = 0x6C, 0x5C, 0xE7
    r = min(255, r + amount)
    b = min(255, b + amount // 2)
    return f"#{r:02x}{g:02x}{b:02x}"


def active_title(script: dict, day_ordinal: int, ab_testing: bool) -> tuple[str, int]:
    """Pick which title variant to use today. Returns (title, variant_index)."""
    variants = [script["title"]] + [v for v in script.get("title_variants", [])
                                    if isinstance(v, str) and v.strip()]
    if not ab_testing or len(variants) == 1:
        return variants[0], 0
    idx = day_ordinal % len(variants)
    return variants[idx], idx


def build_props(script: dict, captions: dict, *, topic: dict,
                hero_image: str = "", title: str | None = None) -> dict:
    accent = script.get("accent", topic.get("accent", "#6C5CE7"))
    return {
        "title": title or script["title"],
        "topicTitle": script["topic_title"],
        "accent": accent,
        "accent2": _shift_hex(accent),
        "pattern": topic.get("pattern", "grid"),
        "heroImage": hero_image or "",
        "audioSrc": "voice.mp3",
        "durationSeconds": captions["duration"],
        "words": captions.get("words", []),
        "lines": script.get("lines", []),
        "points": script.get("points", []),
        "flow": script.get("flow", []),
    }
