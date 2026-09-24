"""Stanford Web Services `stanford_event` JSON:API listings.

Several department sites (KIPAC, SIEPR, Q-FARM, AIMI, Bioengineering) expose
`/jsonapi/views/stanford_events/list_page`. Rows whose source URL points at
events.stanford.edu are Localist mirrors and are skipped.
"""

from __future__ import annotations

from typing import Any

import requests

from .http_util import get
from .normalize import Event, build_event, classify_audience_from_text, classify_audience_names
from .parse_util import (
    JSONAPI_HEADERS,
    abs_url,
    included_index,
    link_uri,
    next_href,
    plain_text,
    rel_labels,
)

VIEW_PATH = "/jsonapi/views/stanford_events/list_page"


def _is_localist_mirror(attrs: dict[str, Any]) -> bool:
    if attrs.get("su_event_localist_id"):
        return True
    for key in ("su_event_source", "su_event_cta"):
        if "events.stanford.edu" in link_uri(attrs.get(key)):
            return True
    return False


def _location(attrs: dict[str, Any]) -> str | None:
    parts: list[str] = []
    loc = attrs.get("su_event_location")
    if isinstance(loc, dict):
        for key in ("organization", "address_line1", "address_line2", "locality"):
            val = (loc.get(key) or "").strip()
            if val and val not in parts:
                parts.append(val)
    alt = (attrs.get("su_event_alt_loc") or "").strip()
    if alt and alt not in " ".join(parts):
        parts.append(alt)
    if parts:
        return ", ".join(parts)
    dek = (attrs.get("su_event_dek") or "").strip()
    if dek and len(dek) <= 80:
        return dek
    return None


def events_from_sws_payload(
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
        if attrs.get("status") is False or _is_localist_mirror(attrs):
            continue
        title = (attrs.get("title") or "").strip()
        when = attrs.get("su_event_date_time") or {}
        start = when.get("value")
        if not title or not start:
            continue
        names = rel_labels(item, "su_event_audience", included)
        location = _location(attrs)
        dek = (attrs.get("su_event_dek") or "").strip()
        body = plain_text(attrs.get("body"))
        description = body or (dek if dek and dek != location else None)
        audience = classify_audience_names(names)
        if audience == "unknown":
            audience = classify_audience_from_text(description, dek, title)
        alias = (attrs.get("path") or {}).get("alias")
        events.append(
            build_event(
                title=title,
                start=start,
                end=when.get("end_value"),
                location=location,
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


def fetch_sws(
    *,
    origin: str,
    source_name: str,
    source_url: str,
    days: int = 30,
    max_pages: int = 8,
) -> list[Event]:
    """Fetch the upcoming SWS event view. ``days`` is applied later by the CLI window."""
    del days  # list_page is already an upcoming view; the CLI window filters it
    url = origin.rstrip("/") + VIEW_PATH
    params: dict[str, Any] | None = {
        "include": "su_event_audience",
        "page[limit]": "50",
    }
    events: list[Event] = []
    seen_pages: set[str] = set()
    seen_ids: set[str] = set()
    for _ in range(max_pages):
        if url in seen_pages:
            break
        seen_pages.add(url)
        payload = _get_json(url, params)
        if payload.get("errors"):
            detail = payload["errors"][0].get("detail") or payload["errors"][0]
            raise RuntimeError(f"{source_name} JSON:API error: {detail}")
        fresh = []
        for item in payload.get("data") or []:
            node_id = item.get("id")
            if node_id and node_id in seen_ids:
                continue
            if node_id:
                seen_ids.add(node_id)
            fresh.append(item)
        if fresh:
            events.extend(
                events_from_sws_payload(
                    {"data": fresh, "included": payload.get("included") or []},
                    source_name=source_name,
                    source_url=source_url,
                    origin=origin,
                )
            )
        href = next_href(payload)
        if not href:
            break
        url = href
        params = None
    return events
