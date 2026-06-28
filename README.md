# 🎬 Daily AI YouTube Shorts — Autopilot

> A fully automated, zero-touch pipeline that researches, scripts, narrates, animates, and publishes one ~50–60 second vertical YouTube Short **every day at 9:00 AM IST and 9:00 PM IST** — rotating across four AI/developer themes, using **only free tools**.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Key Features](#4-key-features)
5. [Repository Structure](#5-repository-structure)
6. [Getting Started (Developers)](#6-getting-started-developers)
7. [Module & Interface Overview](#7-module--interface-overview)
8. [Content & Rendering Workflow](#8-content--rendering-workflow)
9. [Deployment & Environments](#9-deployment--environments)
10. [Logging & Monitoring](#10-logging--monitoring)
11. [Known Challenges / Constraints](#11-known-challenges--constraints)
12. [Contributing Guidelines](#12-contributing-guidelines)
13. [Troubleshooting Guide](#13-troubleshooting-guide)
14. [For Product Managers (Non-Technical Summary)](#14-for-product-managers-non-technical-summary)
15. [Future Enhancements / Roadmap](#15-future-enhancements--roadmap)

---

## 1. Project Overview

**What it is.** An unattended "content factory" for a YouTube channel. Once configured, it runs on a schedule with **no human in the loop**: it pulls the latest AI/developer news, writes an original short-form script, generates an Indian-male voiceover, renders a polished vertical motion-graphics video, and uploads it to YouTube.

**Business problem it solves.** Publishing consistently on YouTube Shorts is the single biggest driver of channel growth, but daily production (research → script → voice → edit → upload) is time-consuming and easy to abandon. This system removes the manual effort entirely and guarantees a fresh, on-brand video every single day.

**Key outcomes delivered:**

- **Consistency** — one new Short per day, automatically, at a fixed time.
- **Freshness** — scripts are built from live news feeds, not static templates.
- **Originality** — rotating hook styles plus a 60-entry "anti-repetition" memory keep videos from feeling templated.
- **Zero marginal cost** — every component runs on a free tier (GitHub Actions, Google Gemini free tier, Microsoft `edge-tts`, open-source Remotion).

> ⚠️ **Honest scope note.** This system *produces and publishes* videos. It does **not** and cannot automate monetization — earning revenue still requires passing the YouTube Partner Program thresholds, which no tool can bypass. See [Known Challenges](#11-known-challenges--constraints).

---

## 2. Architecture Overview

The system has three cooperating layers: a **Python orchestration pipeline** (the brain), a **Remotion/TypeScript renderer** (the visuals), and **GitHub Actions** (the scheduler/runtime). There is **no web server, no HTTP API, and no database** — state is a single JSON file committed back to the repository.

### Data flow

```
                  ┌──────────────────────────────────────────────────────┐
                  │ GitHub Actions: poll + gate + test ──▶ publish steps   │
                  │ targets: 09:00 IST and 21:00 IST (delay-tolerant)      │
                  └───────────────────────────┬──────────────────────────┘
                                              │ run.py stage commands
                       weights + perf hint    ▼
   ┌──────────────┐◀────────────────┌──────────────────┐
   │ analytics.py │  (optional:      │  topic_select.py │  rotate | trending
   │ (YT stats)   │   ENABLE_…)      │                  │────┐
   └──────────────┘                 └──────────────────┘    │ topic of the day
                                                            ▼
                       ┌────────────┐   items+image  ┌─────────────────┐
                       │ fetch_news │───(RSS + ─────▶│ generate_script │
                       │   .py      │   Google News) │  .py (Gemini)   │
                       └────────────┘                └────────┬────────┘
                                          narration            │ script + variants
                                   ┌──────────────┐◀───────────┤
                                   │   tts.py     │  (per-topic voice)
                                   │ (edge-tts)   │
                                   └──────┬───────┘
              voice.mp3 + captions        │   render_props.py (theme + hero + A/B title)
              + render-props.json ───────▶▼
                                   ┌───────────────────────┐
                                   │  Remotion (Short.tsx)  │  → build/out.mp4
                                   │  React/TS + ffmpeg     │   (+ thumb.png, A/B layout)
                                   └───────────┬───────────┘
                                               ▼
                                   ┌───────────────────────┐
                                   │  upload_youtube.py     │ → 📺 YouTube
                                   │  (resumable, retried)  │
                                   └───────────┬───────────┘
                                               │ video_id + variants
                                               ▼
                                   ┌───────────────────────┐
                                   │ state/history.json     │  anti-repetition +
                                   │  committed back to git │  performance memory
                                   └───────────────────────┘
```

### Sequence flow (end-to-end run)

```
GitHub Actions   topics   fetch_news   generate_script   tts   Remotion   upload   YouTube
      │            │           │              │            │       │          │         │
      │─ trigger ─▶│           │              │            │       │          │         │
      │  pick topic│           │              │            │       │          │         │
      │────────────┼─ fetch ──▶│              │            │       │          │         │
      │            │   items ◀─┤              │            │       │          │         │
      │────────────┼───────────┼─ generate ──▶│            │       │          │         │
      │            │           │   script.json◀┤            │       │          │         │
      │────────────┼───────────┼──────────────┼─ speak ───▶│       │          │         │
      │            │           │  voice + captions ◀────────┤       │          │         │
      │────────────┼───────────┼──────────────┼────────────┼ render▶│          │         │
      │            │           │            out.mp4 ◀───────┼───────┤          │         │
      │────────────┼───────────┼──────────────┼────────────┼───────┼─ upload ▶│         │
      │            │           │              │            │       │  id ◀────┼─publish▶│
      │◀─ commit history.json ─┴──────────────┴────────────┴───────┴──────────┘         │
```

**Key design decisions (inferred from the code):**

- **Stateless except for one JSON file.** No database is needed; `state/history.json` is the only persistent state and is version-controlled, making every run reproducible and auditable.
- **Python ↔ Remotion contract via `build/render-props.json`.** The Python layer never touches React; it hands the renderer a single typed JSON props file (validated by a `zod` schema in `Short.tsx`). This cleanly decouples content logic from animation.
- **Audio is the source of truth for video length.** `Short.tsx` computes `durationInFrames` from `durationSeconds`, so the animation always matches the real voiceover length.
- **Resilience first.** Dead RSS feeds are skipped silently, a Google News search is always added as a fallback, Gemini falls back across multiple models, and short/broken audio aborts the run before anything is uploaded.
- **Fail loud, fail early, alert.** A preflight stage validates credentials and binaries before any slow work; each stage raises a typed exception; the orchestrator returns precise exit codes and fires a best-effort failure notification (GitHub issue / Slack).
- **Tested logic, gated releases.** Pure logic is covered by a `pytest` suite that runs as a CI job which must pass before the publish job runs.

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Orchestration / Runtime** | GitHub Actions (cron) | Schedules and runs the daily job on free cloud runners |
| **Pipeline language** | Python 3.11 | End-to-end content pipeline (`pipeline/`) |
| **News ingestion** | `feedparser`, Google News RSS | Pulls fresh, topic-specific source material |
| **Script generation** | Google Gemini (free tier) via `google-genai` | Writes original, non-repetitive 50–60s scripts |
| **Text-to-speech** | Microsoft `edge-tts` (free) | Indian-male voiceover + word-level caption timings |
| **Audio inspection** | `mutagen` | Reads true MP3 length to size the video |
| **Thumbnail** | `Pillow` (PIL) | Generates a themed 1280×720 thumbnail |
| **Video rendering** | Remotion 4 (React 18 + TypeScript), `ffmpeg` | Sleek vertical motion graphics → MP4 |
| **Schema validation** | `zod` | Validates render props passed into the composition |
| **Publishing** | YouTube Data API v3 via `google-api-python-client` | Uploads the video + sets the thumbnail |
| **Auth** | Google OAuth 2.0 refresh token (`google-auth-oauthlib`) | Hands-off, long-lived upload credentials |
| **State store** | JSON file in Git (`state/history.json`) | Anti-repetition memory (no DB) |
| **HTTP client** | `requests` | Timed, retried feed downloads |
| **Config loading** | `python-dotenv` | Loads `.env` for local development |
| **Testing** | `pytest` | Unit tests for pure logic (CI-gated) |
| **Fonts / Assets** | Poppins (bundled), logo/banner SVG+PNG | Brand styling for video and thumbnail |

---

## 4. Key Features

**User-facing (channel) capabilities**

- Publishes one ~50–60s vertical Short twice per day, fully automatically (9 AM and 9 PM IST).
- Rotates across four themes on a fixed daily cycle: **AI news → GitHub/Microsoft Copilot → Claude (Anthropic) → Cursor**.
- Indian-male narration tuned for an **energetic, enthusiastic delivery** with clear pronunciation.
- Polished motion graphics: animated topic chip, two-tone gradient background, animated key-point cards, a boxes-and-arrows "flow" diagram, and a progress bar.
- Auto-generated SEO-friendly title, description with hashtags, and tags.
- Themed custom thumbnail per video.

**Technical / backend capabilities**

- **Anti-repetition engine** — rotating hook styles + a 60-entry history of past titles/hooks fed back into the prompt.
- **Robust news pooling** — pulls a few items from many sources (per-topic RSS + multiple Google News searches), filters narrow topics by keyword so broad feeds can't flood them, applies a 30-day freshness cutoff, de-dupes, and hands the model an 18-item candidate pool.
- **Model fallback** — tries several Gemini models and retries transient rate limits.
- **Fail-safe rendering/upload** — aborts on clearly-broken audio; resumable YouTube upload retries transient 5xx/network errors; thumbnail upload degrades gracefully if the channel isn't verified.
- **Configurable** via environment variables (voice, rate/pitch/volume, model, privacy, review-before-publish, log level, schedule).

**Reliability & operations**

- **Preflight checks** — required env vars and binaries (`ffmpeg`, `node`, `npx`) are validated up front with actionable error messages.
- **Structured logging** — timestamped, levelled logs (`LOG_LEVEL`) across every stage.
- **Typed errors + exit codes** — `0` success, `2` configuration error, `1` other failure.
- **Failure notifications** — opens a GitHub issue (and/or posts to Slack) when a run fails.
- **Weekly credential health check** — a separate scheduled job validates the YouTube token + Gemini key before the daily run needs them.
- **Atomic writes** — generated JSON files are written via temp-file + rename, so a crashed run never leaves a half-written `history.json` or `render-props.json`.
- **CI-gated tests** — a `pytest` job must pass before publishing.

**Optimization & growth features**

- **Smarter topic selection** — `TOPIC_STRATEGY=trending` picks the topic with the most fresh news right now (with a cooldown to keep variety); `rotate` keeps the fixed daily cycle.
- **A/B titles & thumbnails** — the model proposes alternate titles and the pipeline rotates the active title + thumbnail layout per day, recording which variant ran for later analysis.
- **Analytics loop** — optionally pulls public view counts for past uploads and feeds the best-performing styles back into the script prompt and the topic weights.
- **Multi-voice / multi-language** — per-topic voice overrides and a `LANGUAGE` setting (e.g. English, Hindi, Hinglish).
- **Richer visuals** — per-topic background pattern + 2-tone gradient, and an optional faint hero image pulled from the source article.

---

## 5. Repository Structure

```
Youtube_AI_Shorts/
├── .github/workflows/
│   ├── daily-short.yml         # GitHub Actions: test → publish daily, commit history
│   └── healthcheck.yml         # Weekly credential health check
├── pipeline/                   # Python orchestration pipeline (the "brain")
│   ├── run.py                  # Entry point/orchestrator: preflight → … → notify on failure
│   ├── config.py               # Central config, env helpers, atomic JSON writes
│   ├── logging_setup.py        # Structured, levelled logging (LOG_LEVEL)
│   ├── errors.py               # Typed exceptions + retry/backoff decorator
│   ├── preflight.py            # Fail-fast checks (env vars, ffmpeg/node)
│   ├── notify.py               # Best-effort failure alerts (GitHub issue / Slack)
│   ├── healthcheck.py          # Weekly credential validation (CLI)
│   ├── history.py              # Anti-repetition + performance memory (state/history.json)
│   ├── topics.py               # 4-topic rotation + feeds/queries/pattern per topic
│   ├── topic_select.py         # rotate | trending topic selection
│   ├── fetch_news.py           # RSS + Google News ingestion, pooling, filtering, hero image
│   ├── generate_script.py      # Gemini script + variants + analytics hint
│   ├── render_props.py         # Builds Remotion props (theme, hero, A/B title)
│   ├── analytics.py            # Optional view-count feedback loop
│   ├── tts.py                  # edge-tts voiceover (multi-voice) + caption timings
│   ├── thumbnail.py            # Pillow themed 1280×720 thumbnail (A/B layouts)
│   └── upload_youtube.py       # YouTube Data API v3 upload (resumable, retried)
├── tests/                      # pytest suite (rotation, pooling, script, render props, retry…)
├── remotion/                   # Remotion renderer (the "visuals")
│   ├── src/
│   │   ├── Root.tsx            # Composition registration + zod schema + defaults
│   │   ├── Short.tsx           # The animated vertical Short (React/TS)
│   │   └── index.ts            # Remotion entry
│   ├── public/                 # voice.mp3 is copied here for staticFile() at render time
│   ├── package.json            # Remotion 4 + React 18 + TypeScript + zod
│   └── remotion.config.ts      # Render defaults (JPEG frames, concurrency)
├── auth/
│   └── get_token.py            # One-time helper to mint the YouTube OAuth refresh token
├── assets/                     # Fonts (Poppins), logo, banner, sample thumbnail
├── build/                      # Generated artifacts (gitignored): script.json, voice.mp3,
│                               #   captions.json, render-props.json, out.mp4, thumb.png
├── state/
│   └── history.json            # Anti-repetition memory (committed back each run)
├── requirements.txt            # Python runtime dependencies
├── requirements-dev.txt        # Dev/CI dependencies (pytest)
├── pytest.ini                  # Test configuration
├── .env.example                # Template for local secrets / config
└── README.md
```

---

## 6. Getting Started (Developers)

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for Remotion)
- **ffmpeg** (Remotion's encoder) — `sudo apt-get install -y ffmpeg` on Linux
- A **Google account** for: a free **Gemini API key** and **YouTube Data API** OAuth credentials
- A **GitHub** account (to run the scheduled workflow for free)

### Setup instructions

```bash
# 1. Install Python dependencies (add requirements-dev.txt to run the tests)
pip install -r requirements.txt -r requirements-dev.txt

# 2. Install Remotion dependencies
cd remotion && npm install && cd ..

# 3. Create your local env file and fill in the values
cp .env.example .env
```

Generate the YouTube refresh token once (opens a browser to authorize):

```bash
pip install google-auth-oauthlib
python auth/get_token.py client_secret.json
# Copy the printed YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN into .env
# (and into GitHub repo Secrets for the scheduled run)
```

### Configuration

Configuration is environment-variable driven (`pipeline/config.py`). Locally these come from `.env`; in CI they come from **GitHub → Settings → Secrets and variables → Actions**.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini free-tier key (script generation) |
| `YT_CLIENT_ID` | ✅ | — | YouTube OAuth client ID |
| `YT_CLIENT_SECRET` | ✅ | — | YouTube OAuth client secret |
| `YT_REFRESH_TOKEN` | ✅ | — | Long-lived YouTube upload token |
| `YT_PRIVACY` | — | `public` | `public` \| `unlisted` \| `private` |
| `REVIEW_BEFORE_PUBLISH` | — | `false` | `true` uploads as private for manual review |
| `TTS_VOICE` | — | `en-US-JennyNeural` | Clear US female edge-tts voice |
| `TTS_RATE` / `TTS_PITCH` / `TTS_VOLUME` | — | `+16%` / `+8Hz` / `+14%` | Energetic, passionate delivery tuning |
| `GEMINI_MODEL` | — | `gemini-2.5-flash` | Primary model (with fallbacks) |
| `REMOTION_CONCURRENCY` / `REMOTION_GL` | — | all cores / `swangle` | Render-speed flags |
| `REMOTION_SCALE` | — | `0.75` | Render at a codec-safe scale (H264-safe, avoids fractional pixel widths) |
| `REMOTION_IMAGE_FORMAT` / `REMOTION_JPEG_QUALITY` | — | `jpeg` / `68` | Frame extraction speed/quality trade-off |
| `REMOTION_CODEC` / `REMOTION_CRF` / `REMOTION_X264_PRESET` | — | `h264` / `24` / `veryfast` | Encoding speed vs compression trade-off |
| `REMOTION_PIXEL_FORMAT` / `REMOTION_AUDIO_CODEC` | — | `yuv420p` / `aac` | YouTube-friendly output compatibility |
| `LANGUAGE` | — | `English` | Script language (e.g. `Hindi`, `Hinglish`) |
| `TOPIC_STRATEGY` | — | `rotate` | `rotate` (fixed cycle) or `trending` (by news volume) |
| `TOPIC_COOLDOWN` | — | `2` | Trending mode: avoid re-picking recent topics |
| `AB_TESTING` | — | `true` | Rotate title + thumbnail variants daily |
| `ENABLE_ANALYTICS` | — | `false` | Turn on the view-count feedback loop |
| `YT_DATA_API_KEY` | — | — | YouTube Data API key for reading public stats (analytics) |
| `ANALYTICS_LOOKBACK` | — | `30` | How many past uploads to analyze |
| `LOG_LEVEL` | — | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `MIN_AUDIO_SECONDS` | — | `15` | Abort before render/upload if the voiceover is shorter |
| `SLACK_WEBHOOK_URL` | — | — | Optional: post a Slack message on failure |
| `GITHUB_TOKEN` / `GITHUB_REPOSITORY` | — | auto in CI | Used to open a GitHub issue on failure |

> **Secrets are never committed.** `.env`, `client_secret*.json`, and `token.json` are gitignored.
> Invalid `YT_PRIVACY` values fall back to `private` for safety.

### Run instructions

```bash
# Full pipeline (generate → voice → render → upload)
python -m pipeline.run

# Cheap text + voice test (no render, no upload)
python -m pipeline.run --no-render --no-upload

# Generate + render but don't publish
python -m pipeline.run --no-upload

# Run individual stages (same commands used in CI)
python -m pipeline.run --stage script
python -m pipeline.run --stage voice
python -m pipeline.run --stage render
python -m pipeline.run --stage upload

# Preview the animation interactively
cd remotion && npm run studio
```

Run the test suite:

```bash
python -m pytest -q
```

The pipeline exits with **0** on success, **2** on a configuration error (missing
credentials/binaries), and **1** on any other failure — handy for shell/CI checks.

---

## 7. Module & Interface Overview

This project exposes **no HTTP/REST API**. Its "interfaces" are (a) the Python module functions chained by `run.py`, and (b) the external APIs it consumes.

### Internal module contract

| Module | Entry function | Input → Output |
|---|---|---|
| `analytics.py` | `collect()` | past uploads → `(topic_weights, perf_hint)` (optional) |
| `topic_select.py` | `choose_topic(weights)` | strategy → the day's topic dict |
| `fetch_news.py` | `fetch_items(topic)` | topic → de-duped, fresh, on-topic items (with `image`) |
| `generate_script.py` | `generate(topic, items, perf_hint)` | topic + news → `script.json` (`title`, `title_variants`, `description`, `tags`, `lines`, `points`, `flow`, `narration`) |
| `tts.py` | `synthesize(narration, voice)` | text → `voice.mp3` + `captions.json` (`{duration, words[]}`) |
| `render_props.py` | `build_props(...)`, `active_title(...)` | script + captions → typed Remotion props (theme, hero, A/B title) |
| `thumbnail.py` | `make(script, variant)` | script → `build/thumb.png` (or `None`; non-fatal) |
| `upload_youtube.py` | `upload(script)` | `out.mp4` + metadata → YouTube video ID |
| `healthcheck.py` | `main()` | validates YouTube/Gemini credentials → exit code |
| `run.py` | `main(argv)` | orchestrates all stages, or runs one stage via `--stage` |

**Supporting infrastructure modules:** `config.py` (settings, env helpers, atomic writes), `history.py` (anti-repetition + performance memory), `logging_setup.py` (structured logging), `errors.py` (typed exceptions + `retry()` backoff decorator), `preflight.py` (fail-fast checks), `notify.py` (failure alerts), `topics.py` (the four topic definitions + `topic_for`).

### The Python → Remotion data contract (`build/render-props.json`)

Validated by `shortSchema` (zod) in `Short.tsx`:

```jsonc
{
  "title": "AI Innovation? Claude's Code Artifacts Prove It!",
  "topicTitle": "Claude updates",
  "accent": "#E17055",
  "accent2": "#ff9a76",
  "pattern": "rings",
  "heroImage": "https://example.com/article-image.jpg",
  "audioSrc": "voice.mp3",
  "durationSeconds": 56.568,
  "words":  [ { "text": "Most", "start": 0.0, "end": 0.21 } ],
  "lines":  [ "spoken line 1", "spoken line 2" ],
  "points": [ { "heading": "New Claude Tag", "detail": "Mark AI code for review" } ],
  "flow":   [ "You prompt", "Claude drafts", "You review", "Merged" ]
}
```

### External APIs consumed

| Service | Auth | Used for |
|---|---|---|
| Google Gemini (`generativelanguage`) | API key | Script generation |
| Microsoft `edge-tts` endpoint | none | Voice synthesis |
| RSS / Google News | none | News ingestion (+ hero image) |
| YouTube Data API v3 (`videos.insert`, `thumbnails.set`) | OAuth refresh token | Publishing |
| YouTube Data API v3 (`videos.list`) | API key | Reading public view stats (analytics, optional) |

---

## 8. Content & Rendering Workflow

This is the project's equivalent of a "data processing / ML workflow."

**Purpose.** Turn a topic of the day into a finished, published video with no manual steps.

**Input → output flow**

0. **Analytics (optional)** (`analytics.py`) — if enabled, reads public view counts for past uploads and produces per-topic weights + a "what performed well" hint.
1. **Topic selection** (`topic_select.py`) — `rotate` (deterministic daily cycle) or `trending` (the topic with the most fresh news, weighted by past performance, with a cooldown for variety).
2. **News ingestion** (`fetch_news.py`) — pulls from many RSS feeds + multiple Google News searches; applies a 30-day freshness cutoff, keyword filtering for narrow topics, de-duplication, captures a hero image, and returns an 18-item pool.
3. **Script generation** (`generate_script.py`) — Gemini receives the news pool, a hook style, recently-used angles to avoid, the language, and the performance hint; returns strict JSON with a primary `title` plus `title_variants`. History is updated to prevent repetition.
4. **A/B selection** (`render_props.py`) — picks today's active title variant and thumbnail layout, recording the choice in history.
5. **Voiceover** (`tts.py`) — `edge-tts` produces `voice.mp3` and word-level timings using the topic's voice; the run aborts if audio is implausibly short.
6. **Thumbnail** (`thumbnail.py`) — Pillow renders a themed 1280×720 image in the chosen A/B layout.
7. **Rendering** (`remotion/`) — `run.py` writes `render-props.json` (theme + hero image + active title), copies the audio into `remotion/public/`, and invokes `npx remotion render` → `build/out.mp4`.
8. **Publishing & recording** (`upload_youtube.py`) — uploads via the YouTube Data API, sets the thumbnail (best-effort), and writes the `video_id` + timestamp back into history for the analytics loop.

**Trigger mechanism.** Primarily the **scheduler** (GitHub Actions poll cron + gate windows for 09:00 IST and 21:00 IST). Also **manual** via the Actions "Run workflow" button, or locally via `python -m pipeline.run`.

---

## 9. Deployment & Environments

There is a single production runtime: **GitHub Actions**. There are no separate QA/staging deployments; local execution serves as the development environment.

| Environment | Where | How |
|---|---|---|
| **Local / Dev** | Your machine | `.env` + `python -m pipeline.run [--no-render --no-upload]` |
| **Production** | GitHub Actions runner | `.github/workflows/daily-short.yml` with poll + gate windows (09:00/21:00 IST) |
| **Health monitor** | GitHub Actions runner | `.github/workflows/healthcheck.yml` on a weekly cron |

**CI/CD pipeline (`daily-short.yml`):** four jobs.

- **`gate` job:** runs every 15 minutes, allows publish only inside IST target windows (09:00 and 21:00) with delay tolerance, and de-duplicates successful runs per slot.
- **`test` job:** checkout → Python 3.11 → install `requirements.txt` + `requirements-dev.txt` → `pytest`. This job runs only when gate says the slot is open.
- **`publish` job** (`needs: [gate, test]`): checkout → set up Node 20 + Python 3.11 (pip cache) → install ffmpeg → install Python deps → cache & install Remotion deps + headless Chrome → ensure browser → run separate stage steps (**script**, **voice**, **render**, **upload**) → commit `state/history.json` back to the repo.
- **`skip-info` job:** logs why a poll run was skipped (outside window or already completed).
- **Triggers:** `schedule` (cron `*/15 * * * *`) and `workflow_dispatch` (manual).
- **Concurrency guard** prevents overlapping runs; **180-minute** timeout.
- **Permissions:** `actions: read` (slot de-dup lookup), `contents: write` (push history), and `issues: write` (open a failure issue).
- **Feature flags** are passed as repo *Variables* (`TOPIC_STRATEGY`, `AB_TESTING`, `LANGUAGE`, `ENABLE_ANALYTICS`) with safe defaults, plus the optional `YT_DATA_API_KEY` secret.
- **Render speed profile:** CI defaults to a free-runner-optimized Remotion profile (`scale=0.75`, `jpeg-quality=68`, `codec=h264`, `crf=24`, `x264 preset=veryfast`, `pixel-format=yuv420p`, `audio-codec=aac`) and can be tuned via repo Variables (`REMOTION_*`). The scale is snapped to a codec-safe value for H264/H265 to avoid fractional pixel dimensions.

### How slot gating works

`daily-short.yml` polls every 15 minutes, but `gate` only opens execution during two IST windows:

- Morning slot: `09:00` to `12:00` IST (tolerance = 180 minutes)
- Evening slot: `21:00` to `00:00` IST (tolerance = 180 minutes)

Within each window, exactly one successful publish run is allowed. If one run already succeeded for that slot, later poll ticks are skipped.

Example timeline (IST):

- `08:45` poll tick: skipped (`outside_target_window`)
- `09:15` poll tick: gate opens, pipeline runs
- `09:30` poll tick: skipped (`slot_already_completed`)
- `20:45` poll tick: skipped (`outside_target_window`)
- `21:10` poll tick: gate opens, pipeline runs
- `21:30` poll tick: skipped (`slot_already_completed`)

A second workflow, **`healthcheck.yml`**, runs weekly (Mondays 04:00 UTC) and on demand: it validates the YouTube refresh token and Gemini key and opens an issue if either is failing — catching token expiry before it breaks a daily run.

To change publish timing, update the gate window logic and tolerance in `daily-short.yml` (cron remains polling in UTC).

---

## 10. Logging & Monitoring

- **Logging mechanism:** centralized structured logging (`pipeline/logging_setup.py`) emits timestamped, levelled lines (`%(asctime)s | LEVEL | module | message`) at every stage. Verbosity is controlled by `LOG_LEVEL`. Logs appear in the **GitHub Actions run logs** (Actions tab → the run → job steps).
- **Error handling:** every stage raises a typed exception (`ConfigError`, `NewsFetchError`, `ScriptGenerationError`, `TTSError`, `RenderError`, `UploadError`). The orchestrator catches them, logs an actionable message, and returns a precise exit code (`2` config, `1` other). Network reads/uploads retry with exponential backoff; broken/short audio aborts before render/upload; thumbnail failures are non-fatal.
- **Failure alerting:** on failure the run sends a best-effort notification (`pipeline/notify.py`) — a **GitHub issue** (using the Actions-provided `GITHUB_TOKEN`) and/or a **Slack** message (`SLACK_WEBHOOK_URL`). Notification errors never mask the original failure.
- **Where to check:** the **Actions** tab shows pass/fail per day; a green run that produced a new video on the channel confirms success. A failed run shows up as an auto-filed issue (if alerting is configured).

---

## 11. Known Challenges / Constraints

- **OAuth refresh-token expiry.** If the Google OAuth consent screen is in *Testing* mode, the refresh token expires after **7 days** and uploads stop. Publish the app to *Production* to make it long-lived.
- **Gemini quota on corporate accounts.** A Workspace/corporate Google account often has a **zero** free-tier quota (`429 ... limit: 0`); use a personal account's API key.
- **Monetization is not automatable.** The pipeline only produces and uploads; YouTube Partner Program thresholds must be met independently.
- **Repetitive-content policy.** YouTube demonetizes mass-produced content; the anti-repetition design mitigates but does not eliminate this risk.
- **Free-tier dependencies.** `edge-tts` ignores Azure "excited/cheerful" style tags, so energy comes from voice parameters (`TTS_RATE`/`TTS_PITCH`/`TTS_VOLUME`) + script punctuation rather than expressive styles. The default voice is `en-US-JennyNeural`; swap to an Indian voice (e.g. `en-IN-PrabhatNeural` male / `en-IN-NeerjaNeural` female, or `hi-IN-MadhurNeural`) via `TTS_VOICE` or a per-topic override in `topics.py`.
- **Feed drift.** RSS feeds move or go stale; mitigated by generous feed lists + Google News fallbacks (dead feeds are skipped silently).
- **Scheduled-workflow inactivity.** GitHub disables cron workflows after 60 days of repo inactivity; the daily history commit keeps the repo active.

---

## 12. Contributing Guidelines

- **Branching:** `main` is the deployable branch; develop on short-lived feature branches (`feat/...`, `fix/...`) and open a Pull Request.
- **Commits:** imperative, scoped messages (the bot uses `chore: ...`); use `[skip ci]` for non-functional commits that shouldn't trigger runs.
- **Code standards:**
  - Python — keep modules single-purpose and side-effect-light; prefer the existing functional style; fail loudly with actionable messages.
  - TypeScript/Remotion — keep all animation logic in `Short.tsx`; any new prop must be added to **both** `shortSchema` and the Python `write_render_props()`.
- **Testing a change:** run `python -m pytest -q` (must stay green — it gates CI), plus `python -m pipeline.run --no-render --no-upload` (fast) for content changes and `npm run studio` for visual changes, before opening a PR. Add/extend tests under `tests/` for any new pure logic.
- **Never commit secrets.** Use `.env` locally and GitHub Secrets in CI.

---

## 13. Troubleshooting Guide

| Symptom | Likely cause | Fix |
|---|---|---|
| Upload fails after ~a week | Refresh token expired (Testing mode) | Publish OAuth app to Production; re-mint token via `auth/get_token.py` |
| `429 ... limit: 0` from Gemini | Corporate Google account, no free quota | Create a key from a **personal** account; update `GEMINI_API_KEY` |
| Run aborts: "Audio is only Ns" | TTS produced too little audio | Re-run; check `edge-tts` connectivity and the generated `narration` |
| "fetched 0 fresh items" | Feeds down + query too narrow | Broaden the topic's `queries`; verify Google News reachable |
| Thumbnail "skipped" | Channel not phone-verified | Verify at `youtube.com/verify` (upload still succeeds) |
| Remotion render fails in CI | ffmpeg/Chrome not available | Ensure the ffmpeg + `remotion browser ensure` steps ran (check cache) |
| Wrong publish time | Cron is in UTC | Adjust `cron` in `daily-short.yml` (03:30 UTC = 09:00 IST) |
| Run exits with code `2` | Configuration error (missing env var / `ffmpeg` / `node`) | Read the logged message; set the missing secret or install the binary |
| `publish` job skipped | The `test` job failed | Open the `test` job logs; fix the failing test before it will publish |
| No failure issue appears | Alerting not configured | Ensure `issues: write` permission and (optionally) set `SLACK_WEBHOOK_URL` |

**Debugging tips:** set `LOG_LEVEL=DEBUG` for verbose output (including per-feed failures), reproduce locally with `python -m pipeline.run --no-upload`, inspect `build/script.json` and `build/render-props.json` for content issues, and open `remotion/` in Studio to debug visuals.

---

## 14. For Product Managers (Non-Technical Summary)

**What the system does.** Every morning, it acts like a tiny, tireless video team: it reads the day's most relevant AI and developer-tooling news, writes a punchy ~1-minute script, records it in a friendly Indian-male voice, turns it into a sleek animated vertical video, and posts it to YouTube — completely on its own.

**Key workflows.**

1. *Plan* — picks the theme of the day from a fixed four-theme rotation.
2. *Research* — gathers fresh, real news on that theme.
3. *Create* — writes an original, non-repetitive script and narrates it.
4. *Produce* — renders a branded, animated short with on-screen highlights.
5. *Publish* — uploads it (public by default) with a title, description, tags, and thumbnail.

**User journey (high level).** A viewer scrolling YouTube Shorts sees a clean, fast, informative ~1-minute update on the latest in AI or their favorite developer tool, with clear narration and animated highlights — and a prompt to follow for a fresh update daily.

**Business impact & value.**

- **Always-on consistency** — the #1 growth lever on Shorts, with no daily effort.
- **Lower cost** — replaces hours of manual production at essentially $0 running cost.
- **On-brand quality** — consistent look, voice, and structure every day.
- **Defensible originality** — built-in safeguards reduce the "repetitive content" risk that hurts reach and monetization.

**What it does *not* do.** It will not, by itself, generate ad revenue — that depends on meeting YouTube's partner thresholds and on overall content quality and audience growth.

---

## 15. Future Enhancements / Roadmap

**Implemented**

- ✅ **Failure alerting** — opens a GitHub issue and/or posts to Slack on failure.
- ✅ **CI-gated tests** — a `pytest` job must pass before publishing.
- ✅ **Token health check** — weekly job (`healthcheck.yml`) validates credentials early.
- ✅ **Coverage expansion** — tests cover the render-props contract and upload retry paths.
- ✅ **A/B titles & thumbnails** — daily variant rotation, recorded in history for analysis.
- ✅ **Multi-language / multi-voice** — `LANGUAGE` setting + per-topic voice overrides.
- ✅ **Smarter topic selection** — `TOPIC_STRATEGY=trending` weights by live news volume.
- ✅ **Richer visuals** — per-topic patterns/gradients + optional source hero image.
- ✅ **Analytics loop** — optional view-count feedback into scripts + topic weights.

**Still open**

- **True CTR tracking** — the A/B framework records variants; correlating click-through needs YouTube Analytics (impressions/CTR), which requires an added OAuth scope.
- **B-roll / screenshots** — richer hero media beyond the article's feed image.
- **Optional human-in-the-loop** — a one-click review/approve step (scaffolded via `REVIEW_BEFORE_PUBLISH`).

---

*Built entirely on free tools: GitHub Actions · Google Gemini (free tier) · Microsoft edge-tts · Remotion · YouTube Data API.*
