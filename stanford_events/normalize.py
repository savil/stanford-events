"""Shared event schema, hashing, window filter, and dedupe."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

PT = ZoneInfo("America/Los_Angeles")

Event = dict[str, Any]

Audience = Literal["open_to_public", "stanford_only", "unknown"]
AUDIENCE_VALUES: frozenset[str] = frozenset({"open_to_public", "stanford_only", "unknown"})


def make_id(source_url: str, title: str, start_iso: str) -> str:
    raw = f"{source_url}|{title}|{start_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ensure_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as America/Los_Angeles."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=PT)
    return dt.astimezone(PT)


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    text = str(value).strip()
    if not text:
        return None
    dt = date_parser.parse(text)
    return ensure_aware(dt)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return ensure_aware(dt).isoformat()


def short_description(text: str | None, limit: int = 280) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def normalize_audience(value: str | None) -> Audience:
    if value not in AUDIENCE_VALUES:
        raise ValueError(
            f"audience must be one of {sorted(AUDIENCE_VALUES)}, got {value!r}"
        )
    return value  # type: ignore[return-value]


# Text classifiers shared by HTML sources (HAI listing/detail, etc.)
_PUBLIC_RE = re.compile(
    r"(?i)\b(?:"
    r"open\s+to\s+the\s+public|"
    r"open\s+to\s+public|"
    r"open\s+to\s+all(?!\s+stanford)|"
    r"registration\s+open\s+to\s+all|"
    r"general\s+public|"
    r"everyone\s+is\s+welcome|"
    r"free\s+and\s+open\s+to\s+the\s+public"
    r")\b"
)
_STANFORD_ONLY_RE = re.compile(
    r"(?i)\b(?:"
    r"open\s+to\s+stanford(?:\s+community)?(?:\s+members)?|"
    r"for\s+the\s+stanford\s+community|"
    r"stanford\s+community\s+members|"
    r"stanford\s+only|"
    r"stanford\s+students\s+only|"
    r"campus\s+only|"
    r"campus\s+community\s+only|"
    r"sunet(?:[- ]id)?(?:\s+required|\s+login)?"
    r")\b"
)


def classify_audience_from_text(*parts: str | None) -> Audience:
    """Prefer clear public / Stanford-only page signals; else unknown.

    Does not invent a default from weak title keywords alone when both sides
    are silent — callers should pass page/listing text first.
    """
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return "unknown"
    # Stanford-only checked first so "Open to Stanford community" wins over
    # looser "open to …" phrasing.
    if _STANFORD_ONLY_RE.search(text):
        return "stanford_only"
    if _PUBLIC_RE.search(text):
        return "open_to_public"
    return "unknown"


def build_event(
    *,
    title: str,
    start: datetime | str,
    end: datetime | str | None = None,
    location: str | None = None,
    url: str,
    source_name: str,
    source_url: str,
    description: str | None = None,
    audience: str,
) -> Event:
    start_dt = parse_datetime(start)
    if start_dt is None:
        raise ValueError(f"missing start for event: {title!r}")
    end_dt = parse_datetime(end) if end else None
    start_iso = to_iso(start_dt)
    assert start_iso is not None
    return {
        "id": make_id(source_url, title.strip(), start_iso),
        "title": title.strip(),
        "start": start_iso,
        "end": to_iso(end_dt) if end_dt else None,
        "location": (location or "").strip() or None,
        "url": url,
        "source_name": source_name,
        "source_url": source_url,
        "description": short_description(description),
        "audience": normalize_audience(audience),
    }


def window_bounds(days: int = 30, now: datetime | None = None) -> tuple[datetime, datetime]:
    now_pt = ensure_aware(now or datetime.now(tz=PT))
    start = datetime.combine(now_pt.date(), datetime.min.time(), tzinfo=PT)
    end = start + timedelta(days=days + 1)  # exclusive end of day+days
    return start, end


def in_window(event: Event, start: datetime, end: datetime) -> bool:
    ev_start = parse_datetime(event.get("start"))
    if ev_start is None:
        return False
    return start <= ev_start < end


def dedupe(events: list[Event]) -> list[Event]:
    """Dedupe exact ids; within a source_url also collapse same title+day.

    Cross-source duplicates (e.g. HAI talk also on Localist) are kept so reviewers
    can compare parser shapes.
    """
    by_id: dict[str, Event] = {}
    for ev in events:
        by_id.setdefault(ev["id"], ev)

    seen_keys: set[tuple[str, str, str]] = set()
    out: list[Event] = []
    for ev in by_id.values():
        title_key = re.sub(r"\s+", " ", ev["title"].lower()).strip()
        day = (ev.get("start") or "")[:10]
        key = (ev.get("source_url") or "", title_key, day)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(ev)
    out.sort(key=lambda e: (e.get("start") or "", e.get("title") or ""))
    return out


def filter_window(events: list[Event], days: int = 30) -> list[Event]:
    start, end = window_bounds(days=days)
    return [e for e in events if in_window(e, start, end)]


def today_pt() -> date:
    return datetime.now(tz=PT).date()
