# CLAUDE.md

Guidance for AI coding agents working in this repository. Read this before making changes.

## What this project is

A fully-automatic **YouTube Shorts** pipeline that publishes **twice a day** (09:00 and 21:00 IST), unattended in CI. Each run: picks a topic → researches fresh news → writes a 50–60s script with an LLM → narrates it (edge-tts; default `en-US-JennyNeural`, voice configurable) → renders a vertical motion-graphics video → uploads it to YouTube → commits an anti-repetition history back to git. Everything runs on **free tools**.

There is **no web server, no API, and no database**. The only durable state is `state/history.json`, committed back after each run.

## Architecture (three layers)

1. **Python pipeline** (`pipeline/`) — the "brain": research, scripting, voice, orchestration, upload.
2. **Remotion renderer** (`remotion/`, React + TypeScript) — the visuals. Renders to `build/out.mp4`.
3. **GitHub Actions** (`.github/workflows/`) — the scheduler/runtime.

The two layers are **decoupled**: Python never touches React. They communicate through a single typed JSON file, `build/render-props.json`, validated by a `zod` schema in `remotion/src/Short.tsx`.

### End-to-end flow
```
(analytics) → topic_select → fetch_news → generate_script → tts → render_props/thumbnail → Remotion render → upload_youtube → history
```

## Key files

| File | Responsibility |
|---|---|
| `pipeline/run.py` | Orchestrator. Stages: `script`, `voice`, `render`, `upload`. CLI flags `--stage`, `--no-render`, `--no-upload`. Exit codes: **0 ok, 2 config error, 1 other**. |
| `pipeline/config.py` | Single source of truth: paths, env parsing, voice/model settings, toggles, atomic JSON writer. |
| `pipeline/topics.py` | The 4 topics (`ai_news`, `copilot`, `claude`, `cursor`) with feeds, queries, `must_include`, accent, pattern. Rotation by `date.toordinal() % 4`. |
| `pipeline/topic_select.py` | `rotate` (default) vs `trending` strategy; cooldown penalty in pure `pick_by_scores`. |
| `pipeline/fetch_news.py` | RSS + Google News RSS → de-duped, on-topic, time-filtered item pool. Dead feeds skipped silently; empty pool raises `NewsFetchError`. |
| `pipeline/generate_script.py` | Gemini (`google-genai`) → strict-JSON script. Rotating hook styles + recent-title avoidance. Model fallback chain. |
| `pipeline/tts.py` | `edge-tts` → `voice.mp3` + `captions.json`. **Duration from `mutagen`, not word timings.** Default voice `en-US-JennyNeural`; per-topic/env override supported. |
| `pipeline/render_props.py` | Pure builder of `render-props.json` + A/B title picker. |
| `pipeline/thumbnail.py` | Pillow 1280×720 thumbnail, A/B layouts. **Best-effort, never fatal.** |
| `pipeline/upload_youtube.py` | Resumable, retried YouTube Data API v3 upload + best-effort thumbnail set. |
| `pipeline/history.py` | Corruption-tolerant `state/history.json` (anti-repetition + perf memory), capped at 200 entries. |
| `pipeline/preflight.py` | Fail-fast checks for required env vars and binaries (`ffmpeg`, `node`/`npx`). |
| `pipeline/errors.py` | Typed exceptions + `retry()` backoff decorator. |
| `pipeline/notify.py` | Best-effort Slack / GitHub-issue failure alerts. **Never raises.** |
| `pipeline/healthcheck.py` | Weekly credential validation (YT token refresh + Gemini call). |
| `pipeline/analytics.py` | Optional: read public view stats → topic weights + perf hint. No-op unless `ENABLE_ANALYTICS=true`. |
| `remotion/src/Short.tsx` | Scene-based composition: Background → Hook → Cards → Flow → CTA + always-on Subtitles + Progress. `zod` schema lives here. |
| `remotion/src/Root.tsx` | `<Composition>` + defaults; `calculateMetadata` sets `durationInFrames` from `durationSeconds`. |
| `auth/get_token.py` | One-time local OAuth → refresh-token helper. |
| `.github/workflows/daily-short.yml` | Poll → gate to IST slot → test → publish → commit history. |
| `.github/workflows/healthcheck.yml` | Weekly credential health check. |

## Commands

```bash
# Setup (Python)
pip install -r requirements.txt -r requirements-dev.txt

# Run tests (must pass before publish in CI)
python -m pytest -q

# Cheap local test: script + voice only, no render/upload
python -m pipeline.run --no-render --no-upload

# Run a single stage
python -m pipeline.run --stage script
python -m pipeline.run --stage voice
python -m pipeline.run --stage render
python -m pipeline.run --stage upload

# Full run (researches, builds, uploads)
python -m pipeline.run

# Validate the renderer (no browser needed)
cd remotion && npx tsc --noEmit && npx remotion bundle

# Open Remotion Studio to preview visuals with default props
cd remotion && npx remotion studio src/index.ts

# One-time: mint a YouTube refresh token
python auth/get_token.py client_secret.json
```

## Conventions and invariants — DO NOT BREAK THESE

- **Audio is the source of truth for video length.** Duration comes from `mutagen` reading `voice.mp3` (`tts.py`). Never derive length from `words[-1].end` — edge-tts often returns audio with *zero* WordBoundary events. `run.py` hard-aborts if duration `< MIN_AUDIO_SECONDS` (15s).
- **Subtitles are driven by `lines`, not `words`.** `Short.tsx` splits `lines` across the timeline by character weight. Do not gate any scene/caption on `words.length > 0` — that previously produced blank videos.
- **Python ↔ Remotion contract is `build/render-props.json` only.** If you add a field, update both `render_props.build_props()` (producer) and the `shortSchema` + defaults in `Short.tsx`/`Root.tsx` (consumer).
- **All file writes are atomic** (`config.atomic_write_text` / `write_json`). Use them; don't write JSON by hand.
- **Stages are independently runnable and idempotent-ish.** `script` writes `build/script.json` + `build/pipeline-state.json`; later stages read them. Keep that ordering contract.
- **Best-effort steps must never crash the run:** thumbnail generation, custom-thumbnail upload, analytics, and notifications all swallow their own errors and log warnings.
- **Use `google-genai`** (`from google import genai; genai.Client(...)`). The old `google-generativeai` is deprecated — do not reintroduce it.
- **Errors are typed.** Raise the right `PipelineError` subclass (`ConfigError`, `NewsFetchError`, `ScriptGenerationError`, `TTSError`, `RenderError`, `UploadError`) so `run.py` maps it to the correct exit code.
- **Network calls** get a timeout, a User-Agent, and `@retry` backoff. Follow the existing pattern in `fetch_news.py` / `upload_youtube.py`.

## Render profile (performance)

`run.py:render_video()` invokes `npx remotion render` with a free-runner-optimized profile, every knob overridable via `REMOTION_*` env / CI Variables:

| Env var | Default | Notes |
|---|---|---|
| `REMOTION_CONCURRENCY` | `cpu_count - 1` (CI: `2`) | parallel render threads |
| `REMOTION_SCALE` | `0.75` | snapped to a codec-safe value for `h264`/`h265` via `_safe_scale_for_codec` (avoids fractional pixel dims like 720.0003px) |
| `REMOTION_IMAGE_FORMAT` / `REMOTION_JPEG_QUALITY` | `jpeg` / `68` | frame capture |
| `REMOTION_CODEC` / `REMOTION_CRF` / `REMOTION_X264_PRESET` | `h264` / `24` / `veryfast` | encode speed vs size |
| `REMOTION_PIXEL_FORMAT` / `REMOTION_AUDIO_CODEC` | `yuv420p` / `aac` | broad-compatibility output |
| `REMOTION_GL` | `swangle` | headless GL backend |

When you change render flags, update this table and `_safe_scale_for_codec` if you add codecs that need even dimensions.

## Configuration

Local: copy `.env.example` → `.env`. In CI: set GitHub **Secrets** and **Variables**.

Required secrets: `GEMINI_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Optional: `YT_DATA_API_KEY`, `SLACK_WEBHOOK_URL`.

Behaviour toggles (env / CI Variables): `YT_PRIVACY` (public|unlisted|private), `REVIEW_BEFORE_PUBLISH` (true → upload private for manual approval), `TOPIC_STRATEGY` (rotate|trending), `AB_TESTING`, `LANGUAGE`, `ENABLE_ANALYTICS`, `TTS_VOICE`/`TTS_RATE`/`TTS_PITCH`/`TTS_VOLUME`, `LOG_LEVEL`, `MIN_AUDIO_SECONDS`, plus the `REMOTION_*` render knobs above.

Defaults worth knowing: voice `en-US-JennyNeural` (rate `+16%`, pitch `+8Hz`, volume `+14%`), video 1080×1920 @ 30fps, target 50–62s, topic strategy `rotate`. For an Indian voice set `TTS_VOICE=en-IN-PrabhatNeural` (male) or add a per-topic `voice` in `topics.py`.

## Scheduling

`daily-short.yml` polls every 15 min (`cron: "*/15 * * * *"`) and a **gate job** allows exactly one publish per IST slot by inspecting prior successful runs. It publishes **twice a day**: a morning slot at **09:00 IST** and an evening slot at **21:00 IST**, each with a `SLOT_TOLERANCE_MINUTES=180` window (09:00–12:00 and 21:00–00:00). `workflow_dispatch` runs immediately. **To change the run times**, edit the `hour=9` / `hour=21` values in the gate's Python block (keep the IST `UTC+5:30` conversion) and/or the poll cron; the publish job passes the `REMOTION_*` Variables through to the render.

CI installs `ffmpeg`, runs `npx remotion browser ensure`, caches `remotion/node_modules` + `~/.remotion` + `~/.cache/remotion`, then runs the four stages and commits `state/history.json`.

## Testing

`pytest` covers the **pure logic** (`tests/`): topic rotation/cooldown, news de-dup/filter, script JSON extraction/validation/normalization (mocked client), render-props A/B + color shift, thumbnail font fallback, upload retry, history corruption tolerance, analytics. Add a test when you touch pure logic. Network/LLM/render are mocked — never call live services in tests.

## Environment gotchas

- **A real Remotion render needs a Chrome Headless Shell download** (`storage.googleapis.com`) which is often DNS-blocked in restricted sandboxes; committed `node_modules` may also hold a wrong-OS esbuild binary. Validate locally with `tsc --noEmit` + `npx remotion bundle`; the real frame render only runs in CI on a clean `npm ci`.
- **OAuth test-mode refresh tokens expire in ~7 days.** Publish the consent screen to Production. The weekly health check catches expiry early.
- **Corporate Google accounts often have `limit: 0` Gemini free quota.** Use a personal account key. `generate_script.py` falls back across models and emits an actionable error.
- **Monetization cannot be automated** (needs YouTube Partner Program thresholds). Don't add features that imply otherwise.

## Related docs

- `README.md` — full project documentation (architecture diagrams, setup, troubleshooting).
- `BUILD_PROMPT.md` — an instruction set for rebuilding this project from scratch with an AI agent.
