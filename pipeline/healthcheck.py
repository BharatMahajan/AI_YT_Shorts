"""Weekly credential health check.

Validates that the YouTube refresh token can still mint an access token and that
the Gemini key works — BEFORE the daily job actually needs them. Notifies and
exits non-zero on failure so you hear about token expiry the day it happens.

Run:  python -m pipeline.healthcheck
"""
from __future__ import annotations
import os
import sys

from . import config
from .errors import ConfigError
from .logging_setup import get_logger
from .notify import notify_failure

log = get_logger("pipeline.healthcheck")


def check_youtube_token() -> None:
    miss = config.missing_env(config.REQUIRED_ENV_FOR_UPLOAD)
    if miss:
        raise ConfigError("Missing YouTube credentials: " + ", ".join(miss))
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())  # raises if the refresh token is dead/revoked
    if not creds.token:
        raise ConfigError("Token refresh returned no access token.")
    log.info("✓ YouTube refresh token is valid.")


def check_gemini() -> None:
    if config.missing_env(["GEMINI_API_KEY"]):
        raise ConfigError("Missing GEMINI_API_KEY.")
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    next(iter(client.models.list()), None)  # cheap authenticated call
    log.info("✓ Gemini API key works.")


def main(argv=None) -> int:
    problems = []
    try:
        check_youtube_token()
    except Exception as e:  # noqa: BLE001
        problems.append(f"YouTube credential: {e}")
    try:
        check_gemini()
    except Exception as e:  # noqa: BLE001
        problems.append(f"Gemini key: {e}")

    if problems:
        detail = "\n".join(f"- {p}" for p in problems)
        log.error("Health check FAILED:\n%s", detail)
        notify_failure("Weekly health check failed", detail)
        return 1
    log.info("Health check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
