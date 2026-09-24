"""Humanities & Sciences `hs_event` JSON:API (physics, art, statistics, psychology).

Date filters on this field are ignored by these sites, so pages are read newest
first and stopped once events fall before the window. Rows that link out to
events.stanford.edu are Localist mirrors and are skipped.
"""

from __future__ import annotations

from typing import Any

import requests

from .http_util import get
from .normalize import (
    Event,
    build_event,
    classify_audience_from_text,
    classify_audience_names,
    parse_datetime,
    window_bounds,
)
from .parse_util import (
    JSONAPI_HEADERS,
    abs_url,
    included_index,
    link_uri,
    next_href,
    plain_text,
    rel_labels,
)

_GENERIC_TITLE = {
    "colloquium",
    "seminar",
    "title to come",
    "tba",
    "tbd",
}


def _localist_link(attrs: dict[str, Any]) -> bool:
    return "events.stanford.edu" in link_uri(attrs.get("field_hs_event_link"))


def _location(attrs: dict[str, Any]) -> str | None:
    raw = attrs.get("field_hs_event_location") or attrs.get("custm_local_location") or ""
    text = plain_text(raw) if isinstance(raw, str) else plain_text(str(raw) if raw else "")
    if text:
        text = text.replace("\r\n", ", ").replace("\n", ", ")
        text = ", ".join(part.strip() for part in text.split(",") if part.strip())
    return text or None


def events_from_hs_payload(
    payload: dict[str, Any],
    *,
    source_name: str,
    source_url: str,
    origin: str,
) -> list[Event]:
    included = included_index(payload)
    events: list[Event] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        if attrs.get("status") is False or _localist_link(attrs):
            continue
        title = (attrs.get("title") or "").strip()
        when = attrs.get("field_hs_event_date") or {}
        start = when.get("value")
        if not title or not start:
            continue
        speakers = rel_labels(item, "field_hs_event_speaker", included)
        speaker = speakers[0] if speakers else None
        if speaker and title.casefold() in _GENERIC_TITLE:
            title = f"{speaker} — {title}"
        names = rel_labels(item, "field_hs_event_audience", included)
        body = plain_text(attrs.get("body"))
        description = body
        if speaker and speaker.casefold() not in title.casefold():
            description = f"{speaker}. {body}" if body else speaker
        audience = classify_audience_names(names)
        if audience == "unknown":
            audience = classify_audience_from_text(description, title)
        alias = (attrs.get("path") or {}).get("alias")
        events.append(
            build_event(
                title=title,
                start=start,
                end=when.get("end_value"),
                location=_location(attrs),
                url=abs_url(origin, alias) if alias else source_url,
                source_name=source_name,
                source_url=source_url,
                description=description,
                audience=audience,
            )
        )
    return events


def _get_json(url: str, params: dict[str, Any] | None) -> dict[str, Any]:
    try:
        return get(url, params=params, headers=JSONAPI_HEADERS).json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if params and "include" in params and status == 400:
            slim = {k: v for k, v in params.items() if k != "include"}
            return get(url, params=slim, headers=JSONAPI_HEADERS).json()
        raise


def fetch_hs(
    *,
    origin: str,
    source_name: str,
    source_url: str,
    days: int = 30,
    max_pages: int = 5,
) -> list[Event]:
    start_bound, _end_bound = window_bounds(days)
    url = origin.rstrip("/") + "/jsonapi/node/hs_event"
    params: dict[str, Any] | None = {
        "page[limit]": "50",
        "sort": "-field_hs_event_date.value",
        "include": "field_hs_event_audience,field_hs_event_speaker",
    }
    events: list[Event] = []
    seen_pages: set[str] = set()
    for _ in range(max_pages):
        if url in seen_pages:
            break
        seen_pages.add(url)
        payload = _get_json(url, params)
        if payload.get("errors"):
            detail = payload["errors"][0].get("detail") or payload["errors"][0]
            raise RuntimeError(f"{source_name} JSON:API error: {detail}")
        batch = events_from_hs_payload(
            payload,
            source_name=source_name,
            source_url=source_url,
            origin=origin,
        )
        # Newest-first: once a kept-or-skipped row is before the window, stop.
        # Localist mirrors are omitted from `batch`, so also scan raw dates.
        older = False
        for item in payload.get("data") or []:
            when = ((item.get("attributes") or {}).get("field_hs_event_date") or {}).get("value")
            dt = parse_datetime(when)
            if dt is not None and dt < start_bound:
                older = True
                break
        events.extend(batch)
        if older:
            break
        href = next_href(payload)
        if not href:
            break
        url = href
        params = None
    return events
