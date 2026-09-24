"""Small helpers shared by the non-Localist parsers."""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .normalize import PT

JSONAPI_HEADERS = {"Accept": "application/vnd.api+json"}
JSON_HEADERS = {"Accept": "application/json"}


def plain_text(value: Any) -> str | None:
    """Flatten a string or Drupal text-field dict to a single line."""
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("processed") or value.get("value") or ""
    if not isinstance(value, str):
        return None
    text = BeautifulSoup(value, "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([:;,])", r"\1", text)
    return text or None


def link_uri(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("uri") or value.get("url") or "").strip()
    return ""


def abs_url(origin: str, path: str | None) -> str:
    if not path:
        return origin
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = origin if origin.endswith("/") else origin + "/"
    return urljoin(base, path)


def included_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in payload.get("included") or [] if item.get("id")}


def rel_labels(item: dict[str, Any], rel: str, included: dict[str, dict[str, Any]]) -> list[str]:
    raw = ((item.get("relationships") or {}).get(rel) or {}).get("data") or []
    if isinstance(raw, dict):
        raw = [raw]
    labels: list[str] = []
    for ref in raw:
        node = included.get(ref.get("id")) or {}
        attrs = node.get("attributes") or {}
        label = attrs.get("label") or attrs.get("name") or attrs.get("title")
        if label and str(label).strip():
            labels.append(str(label).strip())
    return labels


def next_href(payload: dict[str, Any]) -> str | None:
    nxt = (payload.get("links") or {}).get("next")
    if isinstance(nxt, dict):
        href = nxt.get("href")
        return str(href) if href else None
    if isinstance(nxt, str) and nxt:
        return nxt
    return None


_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)\s*(?:-|–|—|\bto\b)\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)",
    re.I,
)
_TIME_ONE_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", re.I)


def _clock(text: str) -> time | None:
    from dateutil import parser as date_parser

    try:
        return date_parser.parse(text).time().replace(second=0, microsecond=0)
    except (ValueError, OverflowError, TypeError):
        return None


def clocks_from_text(text: str) -> tuple[time | None, time | None]:
    """Pull a start clock and optional end clock out of a listing line."""
    if not text:
        return None, None
    match = _TIME_RANGE_RE.search(text)
    if match:
        return _clock(match.group(1)), _clock(match.group(2))
    one = _TIME_ONE_RE.search(text)
    if one:
        return _clock(one.group(1)), None
    return None, None


def at_clock(day: datetime, clock: time | None) -> datetime:
    """Combine a calendar day with a clock, defaulting to midnight Pacific."""
    base = day.astimezone(PT) if day.tzinfo else day.replace(tzinfo=PT)
    if clock is None:
        clock = time(0, 0)
    return datetime.combine(base.date(), clock, tzinfo=PT)
