"""Fail-fast pre-run checks: surface missing config/deps with actionable messages
*before* the pipeline does any real (and slow) work."""
from __future__ import annotations
import shutil

from . import config
from .errors import ConfigError
from .logging_setup import get_logger

log = get_logger(__name__)


def check_env(require_upload: bool = True) -> None:
    keys = list(config.REQUIRED_ENV_FOR_SCRIPT)
    if require_upload:
        keys += config.REQUIRED_ENV_FOR_UPLOAD
    missing = config.missing_env(keys)
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): " + ", ".join(missing)
            + ". Set them in .env (local) or in GitHub Actions secrets (CI)."
        )


def check_binaries(require_node: bool = True) -> None:
    needed = ["ffmpeg"]
    if require_node:
        needed += ["node", "npx"]
    missing = [b for b in needed if shutil.which(b) is None]
    if missing:
        raise ConfigError(
            "Required executable(s) not found on PATH: " + ", ".join(missing)
            + ". Install ffmpeg and Node.js 20+."
        )


def run(require_upload: bool = True, require_node: bool = True) -> None:
    """Run all preflight checks. Raises ConfigError on the first problem."""
    check_env(require_upload)
    check_binaries(require_node)
    if config.YT_PRIVACY not in config.VALID_PRIVACY:
        log.warning("YT_PRIVACY=%r is invalid; will fall back to 'private'.",
                    config.YT_PRIVACY)
    log.info("Preflight checks passed (upload=%s, node=%s).", require_upload, require_node)
