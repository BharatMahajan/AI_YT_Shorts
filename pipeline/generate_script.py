"""Generate a 50-60s Shorts script with Gemini (free tier), avoiding repetition.

Hardened + extended:
  * Gemini imported lazily (module importable for tests / no-key runs)
  * tolerant JSON extraction + strict validation
  * A/B: asks for `title_variants` alongside the primary title
  * multi-language via config.LANGUAGE
  * optional `perf_hint` from the analytics loop nudges style toward what works
  * history via the shared pipeline.history module
"""
from __future__ import annotations
import json
import os
import re
import random
import time

from . import config
from . import history
from .errors import ScriptGenerationError
from .fetch_news import items_to_context
from .logging_setup import get_logger

log = get_logger(__name__)


def _generate_with_fallback(client, prompt: str):
    models, seen = [], set()
    for m in [config.GEMINI_MODEL, *config.GEMINI_FALLBACK_MODELS]:
        if m not in seen:
            seen.add(m)
            models.append(m)

    last_err = None
    for model in models:
        for attempt in range(2):
            try:
                log.info("Calling Gemini model '%s' (attempt %d).", model, attempt + 1)
                return client.models.generate_content(model=model, contents=prompt)
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                    if "limit: 0" in msg:
                        log.warning("Model '%s' has no free-tier quota; trying next.", model)
                        break
                    log.warning("Rate-limited on '%s'; waiting 20s then retrying.", model)
                    time.sleep(20)
                    continue
                log.warning("Model '%s' failed (%s); trying next.", model, msg[:160])
                break
    raise ScriptGenerationError(
        "Gemini call failed for all models. If you see 'limit: 0', your API key has "
        "no free-tier quota (often a corporate Google account). Create a key from a "
        "personal Google account at https://aistudio.google.com/apikey and update the "
        f"GEMINI_API_KEY secret. Last error: {last_err}"
    )


HOOK_STYLES = [
    "Open with a surprising one-line stat or claim.",
    "Open with a sharp question the viewer is already wondering.",
    "Open by busting a common misconception.",
    "Open with 'Here's what just changed and why it matters'.",
    "Open with a bold contrarian take, then justify it.",
    "Open mid-action, like you're continuing an exciting thought.",
]


def _recent_summary(hist: dict, key: str, n: int = 8) -> str:
    past = history.recent_titles(hist, key, n)
    if not past:
        return "None yet."
    return "\n".join(f"- {e.get('title','')} (hook: {e.get('hook_style','')})" for e in past)


def _extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ScriptGenerationError("Model returned an empty response.")
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(t[start:end + 1])
            except json.JSONDecodeError as e:
                raise ScriptGenerationError(f"Could not parse JSON from model output: {e}")
        raise ScriptGenerationError("Model output contained no JSON object.")


def _validate(data: dict) -> None:
    if not isinstance(data, dict):
        raise ScriptGenerationError("Model output is not a JSON object.")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ScriptGenerationError("Model output missing a non-empty 'title'.")
    lines = data.get("lines")
    if not isinstance(lines, list) or not [x for x in lines if isinstance(x, str) and x.strip()]:
        raise ScriptGenerationError("Model output missing non-empty 'lines'.")


def _normalize(data: dict, topic: dict, hook: str) -> dict:
    data["lines"] = [str(x).strip() for x in data.get("lines", []) if str(x).strip()]
    data["topic"] = topic["key"]
    data["accent"] = topic["accent"]
    data["topic_title"] = topic["title"]
    data["hook_style"] = hook
    data["narration"] = " ".join(data["lines"])
    data.setdefault("description", "")

    if not isinstance(data.get("tags"), list):
        data["tags"] = []
    data["tags"] = [str(t)[:30] for t in data["tags"] if str(t).strip()][:15]

    # A/B title variants (deduped against the primary, capped at 2)
    variants = [str(v).strip() for v in (data.get("title_variants") or [])
                if str(v).strip() and str(v).strip() != data["title"]]
    data["title_variants"] = variants[:2]

    points = []
    for p in (data.get("points") or [])[:4]:
        if isinstance(p, dict) and p.get("heading"):
            points.append({"heading": str(p["heading"])[:28],
                           "detail": str(p.get("detail", ""))[:70]})
        elif isinstance(p, str) and p.strip():
            points.append({"heading": p[:28], "detail": ""})
    if not points:
        points = [{"heading": f"Point {i+1}", "detail": ln[:70]}
                  for i, ln in enumerate(data["lines"][:3])]
    data["points"] = points

    data["flow"] = [str(s)[:18] for s in (data.get("flow") or []) if str(s).strip()][:4]
    return data


def _build_prompt(topic, news_items, hook, avoid, perf_hint) -> str:
    perf_block = f"\nWHAT HAS PERFORMED WELL RECENTLY (lean into this style):\n{perf_hint}\n" if perf_hint else ""
    return f"""You are a passionate US tech host scripting a 50-60 second vertical Short.
Write everything in {config.LANGUAGE}.
Topic theme: {topic['title']}.
Goal: cover {topic['focus']}.

FRESH SOURCE MATERIAL (use only what is real and recent; pick the 1-2 strongest):
{items_to_context(news_items)}

DO NOT repeat angles/openings used recently:
{avoid}
{perf_block}
WRITING RULES:
- {hook}
- ENERGY IS THE PRIORITY: high-energy, enthusiastic, genuinely excited.
- Explain so both developers and non-developers can follow in one listen.
- Write for a TTS engine that inflects on punctuation: punchy hook ending in "!" or "?",
  1-2 more exclamations where excitement is real, plus a quick rhetorical question.
- Vary rhythm: mix very short punchy lines with one or two longer ones.
- Conversational, warm — a real human host talking to a friend, NOT an AI.
- Plain, easy-to-pronounce {config.LANGUAGE}; avoid tongue-twisters and letter-by-letter acronyms.
- 120-140 words total for `lines` (~50-60s spoken). No emojis in spoken lines.
- Concrete: name the actual feature/news and one reason a developer should be excited.
- When introducing technical terms, add a plain-English phrase right after.
- End with a quick, high-energy call to action to follow for daily updates.

ON-SCREEN VISUALS:
- `points`: 3-4 takeaways, each {{"heading": "2-4 words", "detail": "<=9 words"}}.
- `flow`: 3-4 tiny step labels (1-3 words) for a boxes-and-arrows diagram.

Return STRICT JSON only:
{{
  "title": "<=80 chars, punchy, includes a keyword",
  "title_variants": ["alternate title A", "alternate title B"],
  "description": "2-3 lines + 5-8 hashtags incl. #shorts",
  "tags": ["8-12", "lowercase", "keywords"],
  "lines": ["spoken sentence 1", "spoken sentence 2"],
  "points": [{{"heading": "...", "detail": "..."}}],
  "flow": ["step 1", "step 2", "step 3"]
}}"""


def generate(topic: dict, news_items: list[dict], perf_hint: str = "") -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ScriptGenerationError("GEMINI_API_KEY is not set.")
    try:
        from google import genai
    except ImportError as e:  # pragma: no cover
        raise ScriptGenerationError(f"google-genai is not installed: {e}")

    client = genai.Client(api_key=api_key)
    hist = history.load()
    hook = random.choice(HOOK_STYLES)
    avoid = _recent_summary(hist, topic["key"])

    prompt = _build_prompt(topic, news_items, hook, avoid, perf_hint)
    resp = _generate_with_fallback(client, prompt)

    data = _extract_json(getattr(resp, "text", "") or "")
    _validate(data)
    data = _normalize(data, topic, hook)

    config.write_json(config.SCRIPT_FILE, data, indent=2)
    history.prepend(hist, {
        "topic": topic["key"], "title": data["title"], "hook_style": hook,
        "title_variants": data["title_variants"],
    })
    log.info("Generated script: %s", data["title"])
    return data


if __name__ == "__main__":  # pragma: no cover
    from .topic_select import choose_topic
    from .fetch_news import fetch_items
    t = choose_topic()
    print(json.dumps(generate(t, fetch_items(t)), indent=2, ensure_ascii=False))
