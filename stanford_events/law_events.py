"""Stanford Law School events via The Events Calendar REST API."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from .http_util import get
from .normalize import Event, build_event, classify_audience_from_text, window_bounds
from .parse_util import JSON_HEADERS, plain_text

SOURCE_NAME = "Stanford Law"
SOURCE_URL = "https://law.stanford.edu/events/"
API_URL = "https://law.stanford.edu/wp-json/tribe/events/v1/events"


def _aware(value: str | None, timezone: str) -> datetime | None:
    if not value:
        return None
    dt = date_parser.parse(value)
    if dt.tzinfo is None:
        try:
            tz = ZoneInfo(timezone or "America/Los_Angeles")
        except Exception:
            tz = ZoneInfo("America/Los_Angeles")
        dt = dt.replace(tzinfo=tz)
    return dt


def _venue(venue: dict | None) -> str | None:
    if not isinstance(venue, dict):
        return None
    parts = []
    for key in ("venue", "address", "city"):
        val = (venue.get(key) or "").strip()
        if val and val not in parts:
            parts.append(val)
    return ", ".join(parts) or None


def events_from_tribe_payload(payload: dict) -> list[Event]:
    events: list[Event] = []
    for item in payload.get("events") or []:
        if item.get("status") not in (None, "publish"):
            continue
        if item.get("hide_from_listings"):
            continue
        title = plain_text(item.get("title")) or ""
        if not title:
            continue
        timezone = item.get("timezone") or "America/Los_Angeles"
        start = _aware(item.get("start_date"), timezone)
        if start is None:
            continue
        end = _aware(item.get("end_date"), timezone)
        description = plain_text(item.get("description") or item.get("excerpt"))
        venue = item.get("venue") if isinstance(item.get("venue"), dict) else None
        location = _venue(venue)
        if item.get("is_virtual") and not location:
            location = "Online"
        events.append(
            build_event(
                title=title,
                start=start,
                end=end,
                location=location,
                url=item.get("url") or SOURCE_URL,
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                description=description,
                audience=classify_audience_from_text(description, title),
            )
        )
    return events


def fetch_events(days: int = 30) -> list[Event]:
    start, end = window_bounds(days)
    last_day = (end - timedelta(seconds=1)).date().isoformat()
    page = 1
    events: list[Event] = []
    while page <= 6:
        payload = get(
            API_URL,
            params={
                "start_date": start.date().isoformat(),
                "end_date": last_day,
                "per_page": 50,
                "page": page,
                "status": "publish",
            },
            headers=JSON_HEADERS,
        ).json()
        events.extend(events_from_tribe_payload(payload))
        total_pages = int(payload.get("total_pages") or 1)
        if page >= total_pages or not payload.get("events"):
            break
        page += 1
    return events
