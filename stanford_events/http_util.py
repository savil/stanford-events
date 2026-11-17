"""Polite HTTP helpers."""

from __future__ import annotations

import hashlib
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
import requests

USER_AGENT = (
    "StanfordEvents/1.0 (+https://savil.github.io/stanford-events/; "
    "polite daily scrape; not a bot farm)"
)
DEFAULT_TIMEOUT = 30
MIN_INTERVAL_SEC = 0.4

# certifi 2026.10.18 removed emSign Root CA - G1. These hosts chain
# leaf -> InCommon Intermediate CA - DVG2C -> emSign Root TLS CA - G1 ->
# that root. The server already sends the intermediates; only the root
# is missing from certifi. Other hosts stay on certifi alone.
_EMSIGN_ROOT_HOSTS = frozenset(
    {
        "hci.stanford.edu",
        "med.stanford.edu",
    }
)
_EMSIGN_ROOT_PEM = Path(__file__).resolve().parent / "certs" / "emsign_root_ca_g1.pem"

_last_request_at = 0.0


@lru_cache(maxsize=1)
def emsign_ca_bundle() -> str:
    """certifi's CA bundle plus emSign Root CA - G1, as a file path."""
    base = Path(certifi.where()).read_bytes()
    extra = _EMSIGN_ROOT_PEM.read_bytes()
    if not base.endswith(b"\n"):
        base += b"\n"
    payload = base + extra
    digest = hashlib.sha256(payload).hexdigest()[:20]
    path = Path(tempfile.gettempdir()) / f"stanford-events-emsign-{digest}.pem"
    if not path.is_file():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    return str(path)


def verify_for(url: str) -> str | bool:
    """Value for requests' ``verify``. True keeps the certifi default."""
    host = (urlparse(url).hostname or "").rstrip(".")
    if host in _EMSIGN_ROOT_HOSTS:
        return emsign_ca_bundle()
    return True


def get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET with a shared User-Agent and light rate limiting."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_SEC:
        time.sleep(MIN_INTERVAL_SEC - elapsed)
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    resp = requests.get(
        url,
        params=params,
        headers=hdrs,
        timeout=timeout,
        verify=verify_for(url),
    )
    _last_request_at = time.monotonic()
    resp.raise_for_status()
    return resp
