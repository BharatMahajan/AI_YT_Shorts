"""Indian male TTS via edge-tts (free). Emits MP3 + word-level caption timings.

Supports multi-voice: pass `voice` (e.g. a per-topic override) to synthesize.
Hardened: retries transient failures, validates the produced audio.
"""
from __future__ import annotations
import asyncio

import edge_tts

from . import config
from .errors import TTSError, retry
from .logging_setup import get_logger

log = get_logger(__name__)


async def _synthesize_async(text: str, voice: str) -> list[dict]:
    communicate = edge_tts.Communicate(
        text, voice,
        rate=config.TTS_RATE, pitch=config.TTS_PITCH, volume=config.TTS_VOLUME,
    )
    words: list[dict] = []
    wrote_audio = False
    with open(config.AUDIO_FILE, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
                wrote_audio = True
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    if not wrote_audio:
        raise TTSError("edge-tts streamed no audio chunks.")
    return words


@retry(exceptions=(Exception,), tries=3, delay=3.0)
def _run_synthesis(text: str, voice: str) -> list[dict]:
    return asyncio.run(_synthesize_async(text, voice))


def _audio_length_seconds() -> float:
    try:
        from mutagen.mp3 import MP3
        return float(MP3(config.AUDIO_FILE).info.length)
    except Exception as e:  # pragma: no cover
        log.warning("Could not read MP3 length via mutagen (%s).", e)
        return 0.0


def synthesize(narration: str, voice: str | None = None) -> dict:
    """Write voice.mp3 + captions.json; return {'duration': seconds, 'words': [...]}."""
    if not narration or not narration.strip():
        raise TTSError("Narration text is empty.")
    voice = voice or config.TTS_VOICE
    log.info("Synthesizing with voice '%s'.", voice)

    words = _run_synthesis(narration, voice)

    if not config.AUDIO_FILE.exists() or config.AUDIO_FILE.stat().st_size == 0:
        raise TTSError("edge-tts produced an empty audio file.")

    duration = _audio_length_seconds()
    if duration <= 0:
        duration = (words[-1]["end"] if words else 0.0)
    if duration <= 0:
        raise TTSError("Could not determine a valid audio duration.")

    config.write_json(config.CAPTIONS_FILE, {"duration": duration, "words": words})
    log.info("Synthesized voice: %.1fs, %d word timings.", duration, len(words))
    return {"duration": duration, "words": words}
