"""End-to-end daily run:
    (analytics) -> topic -> news -> script -> voice -> render -> upload -> record.

Usage:
  python -m pipeline.run                              # full run + upload
  python -m pipeline.run --no-upload                  # build but don't publish
  python -m pipeline.run --no-render --no-upload      # text + voice only (cheap test)

Exit codes: 0 success, 2 configuration error, 1 any other failure.
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import json
from datetime import date, datetime, timezone

from . import config, history, preflight
from .analytics import collect as collect_analytics
from .errors import ConfigError, PipelineError, RenderError
from .logging_setup import get_logger
from .notify import notify_failure
from .topic_select import choose_topic
from .topics import TOPICS
from .fetch_news import fetch_items, top_image
from .generate_script import generate
from .render_props import active_title, build_props
from .tts import synthesize
from .thumbnail import make as make_thumb

log = get_logger("pipeline.run")

REMOTION_DIR = config.ROOT / "remotion"
RENDER_PROPS = config.BUILD / "render-props.json"
STAGE_STATE = config.BUILD / "pipeline-state.json"


def _safe_scale_for_codec(scale: float, codec: str) -> float:
    """For H264/H265, snap to known-safe scales to avoid floating pixel dimensions."""
    if scale <= 0:
        return 1.0

    normalized_codec = (codec or "").lower()
    if normalized_codec not in {"h264", "h265"}:
        return scale

    # These scales are binary-exact and produce even dimensions for 1080x1920.
    # Using a fixed safe set avoids values like 0.666667 becoming 720.00036px.
    safe_candidates = [1.0, 0.75, 0.5, 0.25]
    return min(safe_candidates, key=lambda s: abs(s - scale))


def _topic_by_key(key: str | None) -> dict | None:
    if not key:
        return None
    for topic in TOPICS:
        if topic.get("key") == key:
            return topic
    return None


def _read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _script_or_fail() -> dict:
    script = _read_json(config.SCRIPT_FILE)
    if not isinstance(script, dict):
        raise PipelineError(
            f"Script artifact missing: {config.SCRIPT_FILE}. Run script stage first."
        )
    return script


def _stage_state() -> dict:
    state = _read_json(STAGE_STATE)
    return state if isinstance(state, dict) else {}


def run_script_stage() -> None:
    preflight.run(require_upload=False, require_node=False)

    weights, perf = collect_analytics()
    topic = choose_topic(weights=weights)
    log.info("Topic of the day: %s (%s)", topic["title"], topic["key"])

    items = fetch_items(topic)
    hero = top_image(items)
    script = generate(topic, items, perf_hint=perf)

    ordinal = date.today().toordinal()
    title, title_idx = active_title(script, ordinal, config.AB_TESTING)
    thumb_variant = (ordinal % config.THUMB_VARIANTS) if config.AB_TESTING else 0
    script["title"] = title
    config.write_json(config.SCRIPT_FILE, script, indent=2)
    history.update_latest(
        history.load(),
        active_title=title,
        title_variant=title_idx,
        thumb_variant=thumb_variant,
    )
    config.write_json(
        STAGE_STATE,
        {
            "topic_key": topic.get("key"),
            "hero_image": hero,
            "thumb_variant": thumb_variant,
        },
    )


def run_voice_stage() -> None:
    preflight.run(require_upload=False, require_node=False)

    script = _script_or_fail()
    state = _stage_state()
    topic = _topic_by_key(state.get("topic_key") or script.get("topic"))
    if topic is None:
        raise PipelineError(
            "Topic context missing for voice stage. Run script stage first."
        )

    voice = topic.get("voice") or config.TTS_VOICE
    captions = synthesize(script.get("narration", ""), voice=voice)
    dur = captions["duration"]
    log.info("Voice length: %.1fs (%d words).", dur, len(captions["words"]))

    if dur < config.MIN_AUDIO_SECONDS:
        raise PipelineError(
            f"Audio is only {dur:.1f}s — too short for a Short (min "
            f"{config.MIN_AUDIO_SECONDS:.0f}s). Aborting before render/upload."
        )
    lo, hi = config.TARGET_SECONDS
    if not (lo - 6 <= dur <= hi + 8):
        log.warning("Length %.1fs outside ideal window %s; continuing.", dur, config.TARGET_SECONDS)

    thumb_variant = state.get("thumb_variant")
    if thumb_variant is None:
        thumb_variant = (date.today().toordinal() % config.THUMB_VARIANTS) if config.AB_TESTING else 0

    config.write_json(
        RENDER_PROPS,
        build_props(script, captions, topic=topic, hero_image=state.get("hero_image")),
    )
    make_thumb(script, variant=int(thumb_variant))  # best-effort; never fatal


def run_render_stage() -> None:
    preflight.run(require_upload=False, require_node=True)
    if not RENDER_PROPS.exists():
        raise RenderError(f"Render props not found: {RENDER_PROPS}. Run voice stage first.")
    if not config.AUDIO_FILE.exists():
        raise RenderError(f"Audio file not found: {config.AUDIO_FILE}. Run voice stage first.")
    render_video()
    log.info("Video ready: %s", config.VIDEO_FILE)


def _video_duration_seconds() -> float:
    captions = _read_json(config.CAPTIONS_FILE)
    if isinstance(captions, dict):
        dur = captions.get("duration")
        if isinstance(dur, (int, float)) and dur > 0:
            return float(dur)
    return 0.0


def _record_upload_log(*, video_id: str, title: str, published_at: str) -> None:
    """Append a human-readable row (size, length, URL, date) for this upload.

    Written to state/upload_log.csv (committed alongside history.json) and,
    when running in GitHub Actions, also echoed into the run's Job Summary.
    """
    size_bytes = config.VIDEO_FILE.stat().st_size if config.VIDEO_FILE.exists() else 0
    size_mb = size_bytes / (1024 * 1024)
    duration_s = _video_duration_seconds()
    url = f"https://youtu.be/{video_id}"

    log_file = config.STATE / "upload_log.csv"
    is_new = not log_file.exists()
    with open(log_file, "a", encoding="utf-8", newline="") as f:
        if is_new:
            f.write("published_at_utc,video_id,youtube_url,size_mb,duration_seconds,title\n")
        safe_title = (title or "").replace('"', "'")
        f.write(
            f'{published_at},{video_id},{url},{size_mb:.2f},{duration_s:.1f},"{safe_title}"\n'
        )

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("### 🎬 Published Short\n")
                f.write(f"- **Title:** {title}\n")
                f.write(f"- **URL:** {url}\n")
                f.write(f"- **Size:** {size_mb:.2f} MB\n")
                f.write(f"- **Length:** {duration_s:.1f}s\n")
                f.write(f"- **Published (UTC):** {published_at}\n")
        except OSError:
            pass


def run_upload_stage() -> None:
    preflight.run(require_upload=True, require_node=False)
    script = _script_or_fail()
    from .upload_youtube import upload

    vid = upload(script)
    published_at = datetime.now(timezone.utc).isoformat()
    history.update_latest(
        history.load(),
        video_id=vid,
        published_at=published_at,
    )
    _record_upload_log(video_id=vid, title=script.get("title", ""), published_at=published_at)
    log.info("Done. Published https://youtu.be/%s", vid)


def render_video() -> None:
    if not REMOTION_DIR.exists():
        raise RenderError(f"Remotion directory not found: {REMOTION_DIR}")
    public = REMOTION_DIR / "public"
    public.mkdir(exist_ok=True)
    (public / "voice.mp3").write_bytes(config.AUDIO_FILE.read_bytes())

    # Fast defaults tuned for free GitHub runners. All knobs are env-overridable.
    concurrency = os.getenv("REMOTION_CONCURRENCY", str(max(1, (os.cpu_count() or 2) - 1)))
    gl = os.getenv("REMOTION_GL", "swangle")
    image_format = os.getenv("REMOTION_IMAGE_FORMAT", "jpeg")
    jpeg_quality = os.getenv("REMOTION_JPEG_QUALITY", "68")
    scale = float(os.getenv("REMOTION_SCALE", "0.75"))
    codec = os.getenv("REMOTION_CODEC", "h264")
    crf = os.getenv("REMOTION_CRF", "24")
    x264_preset = os.getenv("REMOTION_X264_PRESET", "veryfast")
    pixel_format = os.getenv("REMOTION_PIXEL_FORMAT", "yuv420p")
    audio_codec = os.getenv("REMOTION_AUDIO_CODEC", "aac")
    safe_scale = _safe_scale_for_codec(scale, codec)
    if abs(safe_scale - scale) > 1e-6:
        log.info("Adjusted REMOTION_SCALE from %.6f to %.6f for %s even-dimension safety.",
                 scale, safe_scale, codec)

    cmd = [
        "npx", "remotion", "render", "src/index.ts", "Short",
        str(config.VIDEO_FILE),
        f"--props={RENDER_PROPS}",
        f"--concurrency={concurrency}",
        f"--image-format={image_format}",
        f"--jpeg-quality={jpeg_quality}",
        f"--scale={safe_scale}",
        f"--codec={codec}",
        f"--crf={crf}",
        f"--x264-preset={x264_preset}",
        f"--pixel-format={pixel_format}",
        f"--audio-codec={audio_codec}",
        f"--gl={gl}",
    ]
    log.info("Rendering: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=REMOTION_DIR, check=True, shell=(sys.platform == "win32"))
    except subprocess.CalledProcessError as e:
        raise RenderError(f"Remotion render failed (exit {e.returncode}).") from e
    except FileNotFoundError as e:
        raise RenderError(f"Could not run Remotion (is Node/npx installed?): {e}") from e
    if not config.VIDEO_FILE.exists() or config.VIDEO_FILE.stat().st_size == 0:
        raise RenderError("Render completed but produced no output video.")


def _pipeline(args) -> None:
    run_script_stage()
    run_voice_stage()

    if args.no_render:
        log.info("Skipping render (per flag).")
        return
    run_render_stage()

    if args.no_upload:
        log.info("Skipping upload (per flag).")
        return
    run_upload_stage()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Daily AI YouTube Short pipeline.")
    ap.add_argument("--no-render", action="store_true", help="skip the Remotion render")
    ap.add_argument("--no-upload", action="store_true", help="skip the YouTube upload")
    ap.add_argument(
        "--stage",
        choices=["all", "script", "voice", "render", "upload"],
        default="all",
        help="run only a specific stage (default: all)",
    )
    args = ap.parse_args(argv)
    try:
        if args.stage == "all":
            _pipeline(args)
        elif args.stage == "script":
            run_script_stage()
        elif args.stage == "voice":
            run_voice_stage()
        elif args.stage == "render":
            run_render_stage()
        elif args.stage == "upload":
            run_upload_stage()
        return 0
    except ConfigError as e:
        log.error("Configuration error: %s", e)
        notify_failure("Configuration error", str(e))
        return 2
    except PipelineError as e:
        log.error("Pipeline failed: %s", e)
        notify_failure(type(e).__name__, str(e))
        return 1
    except Exception as e:  # noqa: BLE001
        log.exception("Unexpected error.")
        notify_failure("Unexpected error", repr(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
