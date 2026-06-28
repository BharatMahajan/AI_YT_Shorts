"""Best-effort failure notifications. Never raises — notification must not mask
the original error. Channels are opt-in via environment variables:

  SLACK_WEBHOOK_URL   -> posts a message to Slack
  GITHUB_TOKEN + GITHUB_REPOSITORY -> opens a GitHub issue (auto-set in Actions)
"""
from __future__ import annotations
import json
import os
import urllib.request

from .logging_setup import get_logger

log = get_logger(__name__)


def _post(url: str, payload: dict, headers: dict, timeout: int = 15) -> int:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.status


def notify_failure(summary: str, detail: str = "") -> None:
    body = f"{summary}\n\n{detail}".strip()
    sent_any = False

    hook = os.getenv("SLACK_WEBHOOK_URL")
    if hook:
        try:
            _post(hook, {"text": f":rotating_light: Daily AI Short failed\n{body}"},
                  {"Content-Type": "application/json"})
            log.info("Sent Slack failure notification.")
            sent_any = True
        except Exception as exc:  # pragma: no cover - network
            log.warning("Slack notification failed: %s", exc)

    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if token and repo:
        try:
            _post(
                f"https://api.github.com/repos/{repo}/issues",
                {"title": f"Daily AI Short failed: {summary[:80]}",
                 "body": body or summary,
                 "labels": ["automation-failure"]},
                {"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "ai-shorts-bot"},
            )
            log.info("Opened a GitHub issue for the failure.")
            sent_any = True
        except Exception as exc:  # pragma: no cover - network
            log.warning("GitHub issue creation failed: %s", exc)

    if not sent_any:
        log.info("No notification channel configured "
                 "(set SLACK_WEBHOOK_URL, or run in Actions for GITHUB_TOKEN).")
