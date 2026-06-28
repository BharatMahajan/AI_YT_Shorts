"""Upload the rendered Short to YouTube via Data API v3 using a refresh token.

Hardened: validates inputs, retries transient HTTP/transport errors during the
resumable upload, sanitizes privacy, and keeps the custom-thumbnail step
best-effort (it requires a verified channel).
"""
from __future__ import annotations
import os
import random
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config
from .errors import UploadError
from .logging_setup import get_logger

log = get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
_RETRIABLE_STATUS = {500, 502, 503, 504}
_MAX_RETRIES = 5


def _require_credentials() -> None:
    missing = config.missing_env(config.REQUIRED_ENV_FOR_UPLOAD)
    if missing:
        raise UploadError("Missing YouTube credentials: " + ", ".join(missing))


def _service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _resumable_insert(req):
    """Drive a resumable upload, retrying transient failures with backoff."""
    resp = None
    retries = 0
    while resp is None:
        try:
            _, resp = req.next_chunk()
        except HttpError as e:
            if e.resp.status in _RETRIABLE_STATUS and retries < _MAX_RETRIES:
                retries += 1
                sleep = min(2 ** retries + random.random(), 30)
                log.warning("Transient upload error %s; retry %d/%d in %.1fs.",
                            e.resp.status, retries, _MAX_RETRIES, sleep)
                time.sleep(sleep)
                continue
            raise UploadError(f"YouTube API error during upload: {e}") from e
        except (OSError, ConnectionError) as e:
            if retries < _MAX_RETRIES:
                retries += 1
                sleep = min(2 ** retries + random.random(), 30)
                log.warning("Transport error (%s); retry %d/%d in %.1fs.",
                            e, retries, _MAX_RETRIES, sleep)
                time.sleep(sleep)
                continue
            raise UploadError(f"Network error during upload: {e}") from e
    return resp


def upload(script: dict) -> str:
    _require_credentials()
    if not config.VIDEO_FILE.exists() or config.VIDEO_FILE.stat().st_size == 0:
        raise UploadError(f"Rendered video not found or empty: {config.VIDEO_FILE}")

    privacy = "private" if config.REVIEW_BEFORE_PUBLISH else config.safe_privacy()
    body = {
        "snippet": {
            "title": str(script.get("title", "AI Short"))[:100],
            "description": str(script.get("description", ""))[:4900],
            "tags": script.get("tags", [])[:15],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(config.VIDEO_FILE), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    try:
        yt = _service()
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = _resumable_insert(req)
    except UploadError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UploadError(f"Failed to start YouTube upload: {e}") from e

    vid = resp.get("id")
    if not vid:
        raise UploadError(f"Upload returned no video id: {resp}")
    log.info("Uploaded: https://youtu.be/%s (privacy=%s)", vid, privacy)

    _set_thumbnail(yt, vid)
    return vid


def _set_thumbnail(yt, vid: str) -> None:
    thumb = config.BUILD / "thumb.png"
    if not thumb.exists():
        return
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        log.info("Custom thumbnail set.")
    except Exception as e:  # noqa: BLE001 - non-fatal
        log.warning("Thumbnail skipped (%s). Verify channel at youtube.com/verify.", e)


if __name__ == "__main__":  # pragma: no cover
    import json
    upload(json.loads(config.SCRIPT_FILE.read_text(encoding="utf-8")))
