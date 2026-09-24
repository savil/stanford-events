"""Stanford HAI events page scraper (SSR Next.js HTML)."""

from __future__ import annotations

import re
from datetime import datetime, time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .http_util import get
from .normalize import Event, PT, build_event, classify_audience_from_text

SOURCE_NAME = "Stanford HAI"
SOURCE_URL = "https://hai.stanford.edu/events"

DATE_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4}$",
    re.I,
)
TIME_RANGE_RE = re.compile(
    r"(\d{1,2}:\d{2}\s*[AP]M)\s*[-–—]\s*(\d{1,2}:\d{2}\s*[AP]M)",
    re.I,
)
TIME_ONE_RE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.I)
TYPE_LABELS = {
    "seminar",
    "mixer",
    "conference",
    "workshop",
    "lecture",
    "panel",
    "webinar",
    "symposium",
    "conversation",
}


def _parse_time_range(text: str, day: datetime) -> tuple[datetime, datetime | None]:
    text = (text or "").strip()
    m = TIME_RANGE_RE.search(text)
    if m:
        start_t = date_parser.parse(m.group(1)).time()
        end_t = date_parser.parse(m.group(2)).time()
        return (
            datetime.combine(day.date(), start_t, tzinfo=PT),
            datetime.combine(day.date(), end_t, tzinfo=PT),
        )
    m2 = TIME_ONE_RE.search(text)
    if m2:
        start_t = date_parser.parse(m2.group(1)).time()
        return datetime.combine(day.date(), start_t, tzinfo=PT), None
    return datetime.combine(day.date(), time(0, 0), tzinfo=PT), None


def _infer_from_slug(slug: str) -> tuple[time | None, str | None]:
    """Best-effort: '...-430pm-at-coda-e160' → 16:30, 'CoDa E160'."""
    t: time | None = None
    loc: str | None = None
    m = re.search(r"(?<!\d)(\d{1,2})(\d{2})\s*(am|pm)", slug, re.I)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = m.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        t = time(hour, minute)
    m2 = re.search(r"-at-([a-z0-9-]+)$", slug, re.I)
    if m2:
        raw = m2.group(1).replace("-", " ")
        # Light cleanup: coda e160 → CoDa E160-ish
        loc = " ".join(
            w.upper() if re.match(r"^[a-z]\d+$", w, re.I) or w.isdigit() else w.title()
            for w in raw.split()
        )
    return t, loc


def _extract_event(block, *, fallback_title_href=None) -> Event | None:
    link = block.find("a", href=True) if hasattr(block, "find") else None
    if link is None and fallback_title_href:
        link = fallback_title_href
    if link is None:
        return None
    href = link.get("href") or ""
    if "/events/" not in href:
        return None
    slug = href.rstrip("/").split("/")[-1]
    if slug in {"events", ""}:
        return None

    title = link.get_text(" ", strip=True)
    if not title:
        return None

    lines = [ln.strip() for ln in block.get_text("\n", strip=True).split("\n") if ln.strip()]
    date_line = None
    time_line = None
    desc_lines: list[str] = []
    for ln in lines[1:]:
        if DATE_RE.match(ln) and date_line is None:
            date_line = ln
            continue
        if TIME_ONE_RE.search(ln) and time_line is None:
            time_line = ln
            continue
        if ln.lower() in TYPE_LABELS:
            continue
        if date_line and ln != title and not DATE_RE.match(ln):
            # Keep short audience blurbs ("Open to Stanford community members!")
            # and longer description paragraphs from the card.
            if len(ln) > 15:
                desc_lines.append(ln)

    if not date_line:
        return None
    day = date_parser.parse(date_line)

    slug_time, slug_loc = _infer_from_slug(slug)
    if time_line:
        start, end = _parse_time_range(time_line, day)
        # If card was date-only midnight but slug has time, prefer slug
        if start.hour == 0 and start.minute == 0 and end is None and slug_time:
            start = datetime.combine(day.date(), slug_time, tzinfo=PT)
            end = None
    elif slug_time:
        start = datetime.combine(day.date(), slug_time, tzinfo=PT)
        end = None
    else:
        start, end = _parse_time_range("", day)

    # Prefer listing-card page signals (description blurb) over title keywords.
    card_text = " ".join(desc_lines)
    audience = classify_audience_from_text(card_text)
    if audience == "unknown":
        # Title is still on the page (e.g. "For the Stanford Community: …").
        audience = classify_audience_from_text(title)

    desc_line = next((d for d in desc_lines if len(d) > 40), desc_lines[0] if desc_lines else None)

    abs_url = urljoin(SOURCE_URL, href)
    return build_event(
        title=title,
        start=start,
        end=end,
        location=slug_loc,
        url=abs_url,
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        description=desc_line,
        audience=audience,
    )


def fetch_events() -> list[Event]:
    html = get(SOURCE_URL).text
    soup = BeautifulSoup(html, "lxml")

    events: list[Event] = []
    seen_urls: set[str] = set()

    selectors = [
        "[class*='ContentItem_headerText']",
        "[class*='ContentRow_titleColumn']",
    ]
    blocks = []
    for sel in selectors:
        blocks.extend(soup.select(sel))
    if not blocks:
        for a in soup.select('a[href*="/events/"]'):
            parent = a
            for _ in range(4):
                if parent.parent is None:
                    break
                parent = parent.parent
            blocks.append(parent)

    for block in blocks:
        try:
            ev = _extract_event(block)
        except Exception:
            continue
        if ev is None:
            continue
        if ev["url"] in seen_urls:
            # Prefer the copy that has a non-midnight start / location
            existing = next(e for e in events if e["url"] == ev["url"])
            if (existing.get("start") or "").endswith("T00:00:00-07:00") and not (
                ev.get("start") or ""
            ).endswith("T00:00:00-07:00"):
                events.remove(existing)
                events.append(ev)
            elif not existing.get("location") and ev.get("location"):
                existing["location"] = ev["location"]
            # Prefer a classified audience over unknown when merging dupes
            if existing.get("audience") == "unknown" and ev.get("audience") != "unknown":
                existing["audience"] = ev["audience"]
            continue
        seen_urls.add(ev["url"])
        events.append(ev)

    if not events:
        raise RuntimeError("HAI events page: no event cards parsed")
    return events
