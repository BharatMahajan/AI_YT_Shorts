"""Topic rotation. Cycles deterministically by day so the 4 themes alternate.

Each topic carries:
  - feeds:        curated RSS sources (primary signal). Dead/stale feeds are
                  skipped silently by fetch_news, so this list can be generous.
  - queries:      several Google News searches (always-live fallback) that widen
                  the candidate pool so daily scripts stay fresh & non-repetitive.
  - must_include: (narrow topics only) keep only items whose title/summary mention
                  one of these keywords. Lets us add broad AI feeds without
                  flooding the pool with off-topic stories. fetch_news falls back
                  to the full pool if the filter would leave it empty.
"""
from __future__ import annotations
from datetime import date

# Broad AI/tech sources reused across topics (narrow topics stay on-subject via
# must_include, so reusing these here is safe).
_BROAD_AI_FEEDS = [
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://the-decoder.com/feed/",
    "https://www.marktechpost.com/feed/",
    "https://www.unite.ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://analyticsindiamag.com/feed/",
    "https://syncedreview.com/feed/",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
]

TOPICS = [
    {
        "key": "ai_news",
        "title": "Latest AI tech updates",
        "accent": "#6C5CE7",
        "focus": "the single most important AI / tech development in the last few hours",
        "feeds": _BROAD_AI_FEEDS + [
            "https://blog.google/technology/ai/rss/",
            "https://openai.com/news/rss.xml",
            "https://deepmind.google/blog/rss.xml",
            "https://huggingface.co/blog/feed.xml",
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
            "https://www.engadget.com/rss.xml",
            "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
            "https://blogs.microsoft.com/ai/feed/",
            "https://blogs.nvidia.com/feed/",
            "https://bair.berkeley.edu/blog/feed.xml",
            "https://www.kdnuggets.com/feed",
            "https://importai.substack.com/feed",
        ],
        "queries": [
            "artificial intelligence",
            "new AI model release",
            "OpenAI OR Google OR Meta AI announcement",
            "generative AI breakthrough",
            "AI agents OR LLM update",
            "AI launch this week",
            "AI research paper OR benchmark",
        ],
    },
    {
        "key": "copilot",
        "title": "GitHub Copilot updates",
        "accent": "#00B894",
        "focus": "1-2 newest GitHub Copilot / Microsoft Copilot features",
        "must_include": ["copilot"],
        "feeds": [
            "https://github.blog/changelog/label/copilot/feed/",
            "https://github.blog/changelog/feed/",
            "https://github.blog/feed/",
            "https://devblogs.microsoft.com/github/feed/",
            "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",
            "https://devblogs.microsoft.com/visualstudio/feed/",
            "https://devblogs.microsoft.com/devops/feed/",
            "https://devblogs.microsoft.com/dotnet/feed/",
            "https://code.visualstudio.com/feeds/release.xml",
            "https://blogs.windows.com/feed/",
            "https://www.theverge.com/rss/microsoft/index.xml",
            "https://www.neowin.net/feed/",
            "https://mspoweruser.com/feed/",
            "https://www.windowscentral.com/rss",
        ],
        "queries": [
            "GitHub Copilot new feature",
            "Microsoft Copilot update",
            "Copilot Visual Studio Code",
            "Copilot agent mode OR coding agent",
            "Microsoft 365 Copilot feature",
            "Copilot Chat OR Copilot Workspace",
            "GitHub Copilot announcement",
        ],
    },
    {
        "key": "claude",
        "title": "Claude updates",
        "accent": "#E17055",
        "focus": "1-2 newest Claude (Anthropic) features or model releases",
        "must_include": ["claude", "anthropic"],
        "feeds": [
            "https://www.anthropic.com/rss.xml",
            "https://www.anthropic.com/news/rss.xml",
            "https://simonwillison.net/atom/everything/",
        ] + _BROAD_AI_FEEDS,
        "queries": [
            "Anthropic Claude AI update",
            "Claude new model release",
            "Claude new feature Anthropic",
            "Claude Code OR Claude API",
            "Claude Sonnet OR Opus OR Haiku",
            "Anthropic announcement OR research",
            "Claude MCP OR Claude agent",
        ],
    },
    {
        "key": "cursor",
        "title": "Cursor updates",
        "accent": "#0984E3",
        "focus": "1-2 newest Cursor editor features from the changelog",
        "must_include": ["cursor", "anysphere"],
        "feeds": [
            "https://www.cursor.com/changelog/rss.xml",
            "https://cursor.com/changelog/rss.xml",
        ] + _BROAD_AI_FEEDS,
        "queries": [
            "Cursor AI code editor",
            "Cursor editor new feature",
            "Anysphere Cursor update",
            "Cursor agent OR Composer feature",
            "Cursor IDE release",
            "Cursor AI funding OR model",
            "Cursor coding assistant update",
        ],
    },
]


# Per-topic visual pattern (richer visuals) + optional per-topic voice override.
_PATTERNS = {"ai_news": "grid", "copilot": "dots", "claude": "rings", "cursor": "diagonal"}
for _t in TOPICS:
    _t.setdefault("pattern", _PATTERNS.get(_t["key"], "grid"))
    # To use a different voice per topic, set e.g. _t["voice"] = "hi-IN-MadhurNeural"


def topic_for(d: date | None = None) -> dict:
    """Return the topic for the given day (defaults to today), rotating stably."""
    d = d or date.today()
    return TOPICS[d.toordinal() % len(TOPICS)]
