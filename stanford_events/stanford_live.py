"""Stanford Live performances.

The public calendar is a Vue template. Event rows come from
`/api/events/Live`, the same feed the page's `getEventData()` calls.
Localist lists only a subset of these performances.
"""

from __future__ import annotations

from dateutil import parser as date_parser

from .http_util import get
from .normalize import PT, Event, build_event, classify_audience_from_text
from .parse_util import JSON_HEADERS, abs_url, plain_text

SOURCE_NAME = "Stanford Live"
SOURCE_URL = "https://live.stanford.edu/events/calendar"
ORIGIN = "https://live.stanford.edu"
API_URL = ORIGIN + "/api/events/Live"


def _performance_start(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = date_parser.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PT)
    return dt


def events_from_live_payload(payload: list | dict) -> list[Event]:
    rows = payload if isinstance(payload, list) else payload.get("events") or []
    events: list[Event] = []
    for item in rows:
        if not item.get("ShowInCalendar", True):
            continue
        title = plain_text(item.get("DisplayTitle")) or plain_text(item.get("Title")) or ""
        if not title:
            continue
        description = plain_text(item.get("Summary"))
        location = (item.get("Venue") or "").strip() or None
        if item.get("Frost") and location and "frost" not in location.lower():
            location = f"Frost Amphitheater, {location}"
        elif item.get("Frost") and not location:
            location = "Frost Amphitheater"
        url = abs_url(ORIGIN, item.get("EventLink"))
        audience = classify_audience_from_text(description, item.get("Prefix"), title)
        for perf in item.get("Performances") or []:
            start = _performance_start(perf.get("StartDate"))
            if start is None:
                continue
            end = _performance_start(perf.get("EndDate"))
            events.append(
                build_event(
                    title=title,
                    start=start,
                    end=end,
                    location=location,
                    url=url,
                    source_name=SOURCE_NAME,
                    source_url=SOURCE_URL,
                    description=description,
                    audience=audience,
                )
            )
    return events


def fetch_events(days: int = 30) -> list[Event]:
    del days  # one feed; the CLI window drops performances outside today..+30
    payload = get(API_URL, headers=JSON_HEADERS).json()
    if not isinstance(payload, list):
        raise RuntimeError("Stanford Live API did not return a list of events")
    return events_from_live_payload(payload)
