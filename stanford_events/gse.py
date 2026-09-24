"""Stanford Graduate School of Education events via Drupal JSON:API."""

from __future__ import annotations

from typing import Any

from .http_util import get
from .normalize import Event, build_event, classify_audience_from_text, window_bounds
from .parse_util import JSONAPI_HEADERS, abs_url, next_href, plain_text

SOURCE_NAME = "Stanford GSE"
SOURCE_URL = "https://ed.stanford.edu/events"
ORIGIN = "https://ed.stanford.edu"
API_URL = ORIGIN + "/jsonapi/node/event"


def gse_audience(attrs: dict[str, Any], *text: str | None) -> str:
    """Use the admission field. Do not treat 'prospective students' as campus-only."""
    admission = [str(item).lower().replace("-", "_") for item in (attrs.get("field_event_admission") or [])]
    if any(item == "open_to_public" or "open_to_public" in item for item in admission):
        return "open_to_public"
    if any(token in item for item in admission for token in ("only", "community", "internal", "private")):
        return "stanford_only"
    return classify_audience_from_text(*text)


def events_from_gse_payload(payload: dict[str, Any]) -> list[Event]:
    events: list[Event] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        if attrs.get("status") is False or attrs.get("field_hide_from_public"):
            continue
        title = (attrs.get("title") or "").strip()
        slots = attrs.get("field_start_end_datetimes") or []
        if not title or not slots:
            continue
        description = plain_text(attrs.get("field_summary")) or plain_text(attrs.get("body"))
        location = (attrs.get("field_location_name") or "").strip() or None
        alias = (attrs.get("path") or {}).get("alias")
        url = abs_url(ORIGIN, alias) if alias else SOURCE_URL
        audience = gse_audience(attrs, description, title)
        for slot in slots:
            start = (slot or {}).get("value")
            if not start:
                continue
            events.append(
                build_event(
                    title=title,
                    start=start,
                    end=(slot or {}).get("end_value"),
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
    start, end = window_bounds(days)
    params: dict[str, Any] | None = {
        "page[limit]": "50",
        "filter[s][condition][path]": "field_start_end_datetimes.value",
        "filter[s][condition][operator]": ">=",
        "filter[s][condition][value]": start.date().isoformat(),
        "filter[e][condition][path]": "field_start_end_datetimes.value",
        "filter[e][condition][operator]": "<",
        "filter[e][condition][value]": end.date().isoformat(),
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
            raise RuntimeError(f"GSE JSON:API error: {detail}")
        events.extend(events_from_gse_payload(payload))
        href = next_href(payload)
        if not href:
            break
        url = href
        params = None
    return events
