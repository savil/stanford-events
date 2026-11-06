"""Polite HTTP helpers."""

from __future__ import annotations

import sys
import time
from typing import Any

import requests

USER_AGENT = (
    "StanfordEvents/1.0 (+https://savil.github.io/stanford-events/; "
    "polite daily scrape; not a bot farm)"
)
DEFAULT_TIMEOUT = 30
MIN_INTERVAL_SEC = 0.4

# One try plus two retries. Backoff is RETRY_BACKOFF_SEC * 2**(failure-1): 1s, then 2s.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SEC = 1.0

_last_request_at = 0.0


def _is_cert_verify_failure(exc: BaseException) -> bool:
    """True when TLS failed because the certificate did not verify.

    Those failures are deterministic, so another attempt will not help.
    Handshake resets and unexpected EOFs are connection errors and stay retryable.
    """
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if type(current).__name__ == "SSLCertVerificationError":
            return True
        text = str(current).lower()
        if "certificate verify failed" in text or "certificate_verify_failed" in text:
            return True
        current = current.__cause__
    return False


def _is_retryable(exc: BaseException) -> bool:
    """Timeouts and dropped connections. Not HTTP statuses or bad certificates."""
    if _is_cert_verify_failure(exc):
        return False
    return isinstance(
        exc,
        (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ),
    )


def _pace() -> None:
    """Wait out the shared gap since the previous attempt."""
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_SEC:
        time.sleep(MIN_INTERVAL_SEC - elapsed)


def _mark_request() -> None:
    global _last_request_at
    _last_request_at = time.monotonic()


def get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET with a shared User-Agent, a short gap between attempts, and retries.

    Timeouts, connection errors, and TLS handshake drops are retried with
    exponential backoff. Certificate verification failures and HTTP error
    statuses are not retried.
    """
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _pace()
        try:
            resp = requests.get(
                url,
                params=params,
                headers=hdrs,
                timeout=timeout,
            )
        except Exception as exc:
            _mark_request()
            last_error = exc
            if attempt >= MAX_ATTEMPTS or not _is_retryable(exc):
                raise
            delay = RETRY_BACKOFF_SEC * (2 ** (attempt - 1))
            print(
                f"Retrying {url} after {type(exc).__name__} "
                f"(attempt {attempt} of {MAX_ATTEMPTS}, wait {delay:g}s)",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
            continue
        _mark_request()
        resp.raise_for_status()
        return resp
    assert last_error is not None  # the loop either returns or raises
    raise last_error
