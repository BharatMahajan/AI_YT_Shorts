"""Typed exceptions + a reusable retry/backoff helper."""
from __future__ import annotations
import functools
import time

from .logging_setup import get_logger

log = get_logger(__name__)


class PipelineError(Exception):
    """Base class for every error this pipeline raises on purpose."""


class ConfigError(PipelineError):
    """Missing or invalid configuration / credentials / dependencies."""


class NewsFetchError(PipelineError):
    """No usable news items could be gathered for the topic."""


class ScriptGenerationError(PipelineError):
    """The language model failed or returned unusable output."""


class TTSError(PipelineError):
    """Voice synthesis failed or produced unusable audio."""


class RenderError(PipelineError):
    """The Remotion render step failed."""


class UploadError(PipelineError):
    """The YouTube upload failed."""


def retry(exceptions=Exception, tries: int = 3, delay: float = 2.0,
          backoff: float = 2.0, max_delay: float = 30.0):
    """Retry the wrapped callable on `exceptions` with exponential backoff."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _delay = delay
            last_exc = None
            for attempt in range(1, tries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    last_exc = exc
                    if attempt >= tries:
                        break
                    log.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs",
                                getattr(fn, "__name__", "call"), attempt, tries, exc, _delay)
                    time.sleep(_delay)
                    _delay = min(_delay * backoff, max_delay)
            assert last_exc is not None
            raise last_exc
        return wrapper
    return decorator
