"""Polite HTTP helpers."""

from __future__ import annotations

import time
from typing import Any

import requests

USER_AGENT = (
    "StanfordEvents/1.0 (+https://savil.github.io/stanford-events/; "
    "polite daily scrape; not a bot farm)"
)
DEFAULT_TIMEOUT = 30
MIN_INTERVAL_SEC = 0.4

_last_request_at = 0.0


def get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> requests.Response:
    """GET with a shared User-Agent and light rate limiting."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_SEC:
        time.sleep(MIN_INTERVAL_SEC - elapsed)
    resp = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        timeout=timeout,
    )
    _last_request_at = time.monotonic()
    resp.raise_for_status()
    return resp
