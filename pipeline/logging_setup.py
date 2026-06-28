"""Centralized, structured logging for the whole pipeline.

Call get_logger(__name__) anywhere; configuration happens once, lazily.
Level is controlled by the LOG_LEVEL env var (default INFO).
"""
from __future__ import annotations
import logging
import os
import sys

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet chatty third-party libraries.
    for noisy in ("googleapiclient", "google", "google_auth_httplib2",
                  "urllib3", "requests", "feedparser"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str = "pipeline") -> logging.Logger:
    _configure()
    return logging.getLogger(name)
