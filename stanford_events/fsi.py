"""Freeman Spogli Institute events via Drupal JSON:API."""

from __future__ import annotations

from typing import Any

from .http_util import get
from .normalize import Event, build_event, classify_audience_from_text, window_bounds
from .parse_util import JSONAPI_HEADERS, abs_url, next_href, plain_text

SOURCE_NAME = "FSI"
SOURCE_URL = "https://fsi.stanford.edu/events"
ORIGIN = "https://fsi.stanford.edu"
API_URL = ORIGIN + "/jsonapi/node/event"


def events_from_fsi_payload(payload: dict[str, Any]) -> list[Event]:
    events: list[Event] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        if attrs.get("status") is False:
            continue
        title = (attrs.get("title") or "").strip()
        period = attrs.get("field_event_periods") or {}
        start = period.get("value")
        if not title or not start:
            continue
        location = plain_text(attrs.get("field_location"))
        description = plain_text(attrs.get("field_card_select_description")) or plain_text(
            attrs.get("field_og_summary")
        )
        alias = (attrs.get("path") or {}).get("alias")
        events.append(
            build_event(
                title=title,
                start=start,
                end=period.get("end_value"),
                location=location,
                url=abs_url(ORIGIN, alias) if alias else SOURCE_URL,
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                description=description,
                audience=classify_audience_from_text(description, location, title),
            )
        )
    return events


def fetch_events(days: int = 30) -> list[Event]:
    start, end = window_bounds(days)
    params: dict[str, Any] | None = {
        "page[limit]": "50",
        "sort": "field_event_periods.value",
        "filter[s][condition][path]": "field_event_periods.value",
        "filter[s][condition][operator]": ">=",
        "filter[s][condition][value]": start.isoformat(),
        "filter[e][condition][path]": "field_event_periods.value",
        "filter[e][condition][operator]": "<",
        "filter[e][condition][value]": end.isoformat(),
    }
    url = API_URL
    events: list[Event] = []
    seen: set[str] = set()
    for _ in range(6):
        if url in seen:
            break
        seen.add(url)
        payload = get(url, params=params, headers=JSONAPI_HEADERS).json()
        if payload.get("errors"):
            detail = payload["errors"][0].get("detail") or payload["errors"][0]
            raise RuntimeError(f"FSI JSON:API error: {detail}")
        events.extend(events_from_fsi_payload(payload))
        href = next_href(payload)
        if not href:
            break
        url = href
        params = None
    return events
