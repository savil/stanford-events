"""Localist (events.stanford.edu) JSON API scraper."""

from __future__ import annotations

from typing import Any

from .http_util import get
from .normalize import Audience, Event, build_event, classify_audience_names, parse_datetime

SOURCE_NAME = "Stanford Events (Localist)"
SOURCE_URL = "https://events.stanford.edu/"
API_URL = "https://events.stanford.edu/api/2/events"

# Bing Concert Hall place/venue id discovered via /api/2/places.
# A 2026-09-24 spot-check found Bing's in-window events already in the
# unfiltered feed; the extra venue query stays so a venue-only row is not lost.
BING_VENUE_ID = 37946728938604
BING_SOURCE_URL = "https://events.stanford.edu/bing_concert_hall"


def _audience_names(event: dict[str, Any]) -> list[str]:
    filters = event.get("filters") or {}
    raw = filters.get("event_audience") or []
    names: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def classify_localist_audience(event: dict[str, Any]) -> Audience:
    """Map Localist filters.event_audience (+ no forced default).

    Uses the API `filters.event_audience` list already present on each event
    payload. Clear public tags → open_to_public; campus-only tags without
    public tags → stanford_only; missing / unrecognized → unknown.
    """
    return classify_audience_names(_audience_names(event))


def _location(event: dict[str, Any]) -> str | None:
    parts = []
    name = (event.get("location_name") or "").strip()
    room = (event.get("room_number") or "").strip()
    address = (event.get("address") or "").strip()
    if name:
        parts.append(name)
    if room:
        parts.append(f"Room {room}" if not room.lower().startswith("room") else room)
    if address and address not in " ".join(parts):
        parts.append(address)
    return ", ".join(parts) if parts else None


def _event_url(event: dict[str, Any]) -> str:
    for key in ("localist_url", "url"):
        val = event.get(key)
        if val and str(val).startswith("http"):
            return str(val)
    urlname = event.get("urlname")
    if urlname:
        return f"https://events.stanford.edu/event/{urlname}"
    return SOURCE_URL


def _instances_to_events(
    event: dict[str, Any],
    *,
    source_name: str,
    source_url: str,
) -> list[Event]:
    title = (event.get("title") or "").strip()
    if not title:
        return []
    desc = event.get("description_text") or event.get("description")
    loc = _location(event)
    url = _event_url(event)
    audience = classify_localist_audience(event)
    out: list[Event] = []
    instances = event.get("event_instances") or []
    if not instances:
        # Fall back to first/last date if instances missing
        start = event.get("first_date")
        if not start:
            return []
        out.append(
            build_event(
                title=title,
                start=start,
                end=None,
                location=loc,
                url=url,
                source_name=source_name,
                source_url=source_url,
                description=desc,
                audience=audience,
            )
        )
        return out

    for wrap in instances:
        inst = wrap.get("event_instance") or wrap
        start = inst.get("start")
        if not start:
            continue
        end = inst.get("end")
        # All-day events often have midnight start and null end — keep as-is
        out.append(
            build_event(
                title=title,
                start=start,
                end=end,
                location=loc,
                url=url,
                source_name=source_name,
                source_url=source_url,
                description=desc,
                audience=audience,
            )
        )
    return out


def _fetch_pages(
    *,
    days: int,
    pp: int = 100,
    extra_params: dict[str, Any] | None = None,
    max_pages: int = 15,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        params: dict[str, Any] = {"days": days, "pp": pp, "page": page}
        if extra_params:
            params.update(extra_params)
        data = get(API_URL, params=params).json()
        batch = data.get("events") or []
        for wrap in batch:
            ev = wrap.get("event") or wrap
            events.append(ev)
        page_info = data.get("page") or {}
        next_page = page_info.get("next_page")
        if not next_page:
            break
        page = int(next_page)
    return events


def fetch_events(days: int = 30) -> list[Event]:
    """
    Fetch main Localist feed + Bing Concert Hall venue feed, normalize instances.

    Prefer /api/2/events over HTML. Days param is Localist's rolling window.
    """
    # Request a slightly wider Localist window so PT day-boundary filtering is safe
    raw_main = _fetch_pages(days=days + 1)
    raw_bing = _fetch_pages(days=days + 1, extra_params={"venue_id": BING_VENUE_ID})

    out: list[Event] = []
    for ev in raw_main:
        out.extend(_instances_to_events(ev, source_name=SOURCE_NAME, source_url=SOURCE_URL))
    for ev in raw_bing:
        out.extend(
            _instances_to_events(
                ev,
                source_name="Bing Concert Hall (Localist)",
                source_url=BING_SOURCE_URL,
            )
        )
    # Drop instances with unparsable starts (normalize raises) — already raised
    # Filter out instances that Localist returned outside our interest by start date
    return out
