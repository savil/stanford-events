"""CCRMA event calendar (Drupal month view plus event pages)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .http_util import get
from .normalize import Event, PT, build_event, classify_audience_from_text, window_bounds

SOURCE_NAME = "CCRMA"
SOURCE_URL = "https://ccrma.stanford.edu/calendar"
ORIGIN = "https://ccrma.stanford.edu"

_DAY_ID = re.compile(r"(\d{4}-\d{2}-\d{2})$")
_WHEN = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)"
    r"(?:\s*-\s*(\d{1,2}:\d{2}\s*[ap]m))?",
    re.I,
)


def _field_text(soup: BeautifulSoup, css: str) -> str:
    node = soup.select_one(css)
    if node is None:
        return ""
    text = node.get_text(" ", strip=True)
    return re.sub(
        r"^(Date|Location|Event Type|Intended Audience)\s*:\s*",
        "",
        text,
        count=1,
        flags=re.I,
    ).strip()


def month_keys(days: int) -> list[str]:
    start, end = window_bounds(days)
    last = (end - timedelta(seconds=1)).date()
    year, month = start.year, start.month
    keys: list[str] = []
    while (year, month) <= (last.year, last.month):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return keys


def event_urls_from_month(html: str, page_url: str, *, start: date, end: date) -> list[str]:
    """Return absolute event URLs whose calendar cell falls in ``[start, end]``."""
    soup = BeautifulSoup(html, "lxml")
    found: list[str] = []
    seen: set[str] = set()
    for cell in soup.find_all("td", id=True):
        match = _DAY_ID.search(cell["id"])
        if not match:
            continue
        day = date.fromisoformat(match.group(1))
        if day < start or day > end:
            continue
        for link in cell.find_all("a", href=True):
            href = link["href"]
            if "/events/" not in href or "/calendar" in href:
                continue
            abs_link = urljoin(page_url, href)
            if abs_link not in seen:
                seen.add(abs_link)
                found.append(abs_link)
    return found


def event_from_detail(html: str, url: str) -> Event | None:
    soup = BeautifulSoup(html, "lxml")
    when = _WHEN.search(_field_text(soup, ".field-field-event-date"))
    if not when:
        return None
    day = date_parser.parse(when.group(1)).date()
    start_t = date_parser.parse(when.group(2))
    start = datetime_on(day, start_t)
    end = None
    if when.group(3):
        end = datetime_on(day, date_parser.parse(when.group(3)))
    heading = soup.find("h1")
    title = heading.get_text(" ", strip=True) if heading else ""
    if not title or title.lower() == "ccrma":
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else ""
        title = re.sub(r"\s*\|\s*CCRMA\s*$", "", title).strip()
    if not title:
        return None
    location = _field_text(soup, ".field-field-location") or None
    audience_text = _field_text(soup, ".field-field-intended-audience")
    body_node = soup.select_one(".node")
    description = None
    if body_node is not None:
        paragraphs = [p.get_text(" ", strip=True) for p in body_node.find_all("p")]
        description = next((p for p in paragraphs if len(p) > 40), None)
    return build_event(
        title=title,
        start=start,
        end=end,
        location=location,
        url=url,
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        description=description,
        audience=classify_audience_from_text(audience_text, description),
    )


def datetime_on(day: date, parsed: datetime) -> datetime:
    return datetime.combine(day, parsed.time().replace(second=0, microsecond=0), tzinfo=PT)


def fetch_events(days: int = 30, *, max_details: int = 25) -> list[Event]:
    start, end = window_bounds(days)
    last = (end - timedelta(seconds=1)).date()
    urls: list[str] = []
    seen: set[str] = set()
    for key in month_keys(days):
        page = f"{ORIGIN}/calendar/{key}"
        html = get(page).text
        for link in event_urls_from_month(html, page, start=start.date(), end=last):
            if link not in seen:
                seen.add(link)
                urls.append(link)
    events: list[Event] = []
    for link in urls[:max_details]:
        try:
            detail = get(link).text
        except Exception:
            continue
        ev = event_from_detail(detail, link)
        if ev is not None:
            events.append(ev)
    if urls and not events:
        raise RuntimeError("CCRMA calendar linked events but none could be parsed")
    return events
