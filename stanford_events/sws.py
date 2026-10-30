"""Stanford Web Services `stanford_event` JSON:API listings.

Several department sites (KIPAC, SIEPR, Q-FARM, AIMI, Bioengineering) expose
`/jsonapi/views/stanford_events/list_page`. Rows whose source URL points at
events.stanford.edu are Localist mirrors and are skipped.

On some hosts that view display returns a fast nginx 502 (the HTML rendering
of the same display, and other JSON:API resources, still answer 200). Those
sources then parse the upcoming HTML list and read `su_event_audience` from
each event page.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .http_util import get
from .normalize import (
    Event,
    build_event,
    classify_audience_from_text,
    classify_audience_names,
    in_window,
    parse_datetime,
    short_description,
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

VIEW_PATH = "/jsonapi/views/stanford_events/list_page"
# Gateway HTML from nginx, not a Drupal JSON:API error document. Retrying the
# same view does not help; the HTML listing below is the same display.
_GATEWAY_STATUSES = frozenset({502, 503, 504})
_MAX_DETAIL_PAGES = 40


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


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+,", ",", text)
    cleaned = re.sub(r",(\S)", r", \1", cleaned)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned or None


def _node_text(node: Any) -> str | None:
    for br in node.find_all("br"):
        br.replace_with(", ")
    return _clean(node.get_text(" ", strip=True))


def _card_location(card: Any) -> str | None:
    parts: list[str] = []
    for sel in (
        ".views-field-su-event-location",
        ".event-list_item__dek",
        ".su-event-dek",
        ".views-field-su-event-address",
    ):
        node = card.select_one(sel)
        if node is None:
            continue
        text = _node_text(node)
        if text and text not in parts and not any(text in part for part in parts):
            parts.append(text)
    return ", ".join(parts) or None


def _is_localist_url(url: str) -> bool:
    return "events.stanford.edu" in (urlparse(url).netloc or "")


def events_from_sws_html(
    html: str,
    *,
    page_url: str,
    source_name: str,
    source_url: str,
    origin: str,
) -> list[Event]:
    """Parse one rendered `stanford_events` / `list_page` HTML page."""
    del origin  # event URLs are resolved against the page that listed them
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    for card in soup.select("article.su-event-list-item"):
        link = card.select_one("h3 a[href]") or card.select_one("h2 a[href]")
        times = [node for node in card.select("time[datetime]") if node.get("datetime")]
        if link is None or not times:
            continue
        title = link.get_text(" ", strip=True)
        url = urljoin(page_url, link["href"])
        if not title or _is_localist_url(url):
            continue
        start = times[0]["datetime"]
        end = times[1]["datetime"] if len(times) > 1 else None
        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end) if end else None
        if start_dt and end_dt and end_dt < start_dt:
            end = None
        location = _card_location(card)
        sub = card.select_one(".event-list-item__subheadline")
        description = _clean(sub.get_text(" ", strip=True)) if sub else None
        if description and location and description == location:
            description = None
        events.append(
            build_event(
                title=title,
                start=start,
                end=end,
                location=location,
                url=url,
                source_name=source_name,
                source_url=source_url,
                description=description,
                audience=classify_audience_from_text(description, location, title),
            )
        )
    return events


def audience_names_from_event_page(html: str) -> list[str]:
    """Names from the event page's "This event is open to" block."""
    soup = BeautifulSoup(html, "lxml")
    block = soup.select_one(".su-event-audience")
    if block is None:
        return []
    names = [
        _clean(div.get_text(" ", strip=True))
        for div in block.find_all("div", recursive=False)
    ]
    names = [name for name in names if name]
    if names:
        return names
    text = _clean(block.get_text(" ", strip=True))
    return [text] if text else []


def description_from_event_page(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one(".su-event-body")
    if body is None:
        return None
    return plain_text(body.decode_contents())


def _page_is_events_view(soup: Any) -> bool:
    if soup.select_one(".stanford-events") or soup.select_one(".view-empty"):
        return True
    text = soup.get_text(" ", strip=True).lower()
    return "no upcoming events" in text or "there are no events" in text


def _next_listing_url(soup: Any, page_url: str) -> str | None:
    link = soup.select_one("a[rel='next']") or soup.select_one("a[title='Load more items']")
    href = link.get("href") if link else None
    if not href:
        return None
    return urljoin(page_url, href)


def _same_site(origin: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(origin).netloc


def _enrich_from_event_pages(
    events: list[Event],
    *,
    origin: str,
    start_bound: Any,
    end_bound: Any,
) -> None:
    """Fill audience (and the body) from event pages inside the CLI window."""
    fetched = 0
    for event in events:
        if fetched >= _MAX_DETAIL_PAGES:
            break
        if not in_window(event, start_bound, end_bound):
            continue
        if not _same_site(origin, event["url"]):
            continue
        fetched += 1
        try:
            html = get(event["url"]).text
        except requests.HTTPError:
            continue
        names = audience_names_from_event_page(html)
        body = description_from_event_page(html)
        if body:
            event["description"] = short_description(body)
        audience = classify_audience_names(names) if names else "unknown"
        if audience == "unknown":
            audience = classify_audience_from_text(
                body,
                event.get("description"),
                event.get("location"),
                event.get("title"),
            )
        event["audience"] = audience


def _fetch_listing_html(
    *,
    origin: str,
    source_name: str,
    source_url: str,
    days: int,
    max_pages: int,
) -> list[Event]:
    start_bound, end_bound = window_bounds(days)
    events: list[Event] = []
    seen_pages: set[str] = set()
    seen_urls: set[str] = set()
    page_url = source_url
    for _ in range(max_pages):
        if page_url in seen_pages:
            break
        seen_pages.add(page_url)
        html = get(page_url).text
        soup = BeautifulSoup(html, "lxml")
        batch = events_from_sws_html(
            html,
            page_url=page_url,
            source_name=source_name,
            source_url=source_url,
            origin=origin,
        )
        if not batch and not events and not _page_is_events_view(soup):
            raise RuntimeError(
                f"{source_name} events page did not contain the Stanford events list"
            )
        fresh: list[Event] = []
        for event in batch:
            if event["url"] in seen_urls:
                continue
            seen_urls.add(event["url"])
            fresh.append(event)
        events.extend(fresh)
        nxt = _next_listing_url(soup, page_url)
        if not nxt or not fresh:
            break
        starts = [parse_datetime(event["start"]) for event in fresh]
        starts = [start for start in starts if start is not None]
        # Later pages of this view are further in the future.
        if starts and min(starts) >= end_bound:
            break
        page_url = nxt
    _enrich_from_event_pages(
        events,
        origin=origin,
        start_bound=start_bound,
        end_bound=end_bound,
    )
    return events


def _fetch_view(
    *,
    origin: str,
    source_name: str,
    source_url: str,
    max_pages: int,
) -> list[Event]:
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


def fetch_sws(
    *,
    origin: str,
    source_name: str,
    source_url: str,
    days: int = 30,
    max_pages: int = 8,
) -> list[Event]:
    """Fetch the upcoming SWS event view.

    ``list_page`` is already an upcoming view. ``days`` bounds the HTML
    fallback (pager stop, and which event pages are opened for audience).
    The CLI applies the same window again.
    """
    try:
        return _fetch_view(
            origin=origin,
            source_name=source_name,
            source_url=source_url,
            max_pages=max_pages,
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in _GATEWAY_STATUSES:
            raise
        return _fetch_listing_html(
            origin=origin,
            source_name=source_name,
            source_url=source_url,
            days=days,
            max_pages=max_pages,
        )
