"""HTML listings that are not Localist mirrors and have no JSON feed.

Neuroscience, the Humanities Center, GSB, Stanford Health Library, and SLAC.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .http_util import get
from .normalize import Event, PT, build_event, classify_audience_from_text, today_pt
from .parse_util import at_clock, clocks_from_text

_MONTH = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_DATE_RE = re.compile(
    rf"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,\s+)?({_MONTH})\.?\s+(\d{{1,2}})"
    rf"(?:st|nd|rd|th)?(?:\s*,?\s*(20\d{{2}}))?",
    re.I,
)


def _fetch_pages(url: str, *, max_pages: int = 3) -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _ in range(max_pages):
        if url in seen:
            break
        seen.add(url)
        html = get(url).text
        pages.append((url, html))
        soup = BeautifulSoup(html, "lxml")
        nxt = soup.select_one("a[rel='next']")
        href = nxt.get("href") if nxt else None
        if not href:
            break
        url = urljoin(url, href)
    return pages


def parse_neuroscience(html: str, page_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    for card in soup.select("article.node--type-event"):
        link = card.select_one("h4 a[href]") or card.select_one("a[href]")
        if link is None:
            continue
        title = link.get_text(" ", strip=True)
        times = card.select("time")
        if not times or not times[0].get("datetime"):
            continue
        start = date_parser.parse(times[0]["datetime"])
        end = None
        if len(times) > 1 and times[1].get("datetime"):
            end = date_parser.parse(times[1]["datetime"])
        else:
            _start_clock, end_clock = clocks_from_text(card.get_text(" ", strip=True))
            if end_clock is not None:
                end = at_clock(start, end_clock)
        loc_node = card.select_one(".location")
        location = loc_node.get_text(" ", strip=True) if loc_node else None
        blurb = card.get_text(" ", strip=True)
        events.append(
            build_event(
                title=title,
                start=start,
                end=end,
                location=location,
                url=urljoin(page_url, link["href"]),
                source_name="Wu Tsai Neurosciences",
                source_url="https://neuroscience.stanford.edu/events",
                description=None,
                audience=classify_audience_from_text(blurb),
            )
        )
    return events


def fetch_neuroscience(days: int = 30) -> list[Event]:
    del days
    url = "https://neuroscience.stanford.edu/events"
    events: list[Event] = []
    for page_url, html in _fetch_pages(url):
        events.extend(parse_neuroscience(html, page_url))
    if not events:
        raise RuntimeError("Wu Tsai Neurosciences events page: no event cards parsed")
    return events


def parse_humanities_center(html: str, page_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    for row in soup.select(".views-row"):
        link = row.select_one(".views-field-title a[href]")
        times = row.select("time[datetime]")
        if link is None or not times:
            continue
        start = date_parser.parse(times[0]["datetime"])
        end = date_parser.parse(times[1]["datetime"]) if len(times) > 1 else None
        loc_node = row.select_one(".views-field-field-event-location")
        location = loc_node.get_text(" ", strip=True) if loc_node else None
        topic = row.select_one(".views-field-field-topic")
        description = topic.get_text(" ", strip=True) if topic else None
        events.append(
            build_event(
                title=link.get_text(" ", strip=True),
                start=start,
                end=end,
                location=location,
                url=urljoin(page_url, link["href"]),
                source_name="Stanford Humanities Center",
                source_url="https://shc.stanford.edu/stanford-humanities-center/events",
                description=description,
                audience=classify_audience_from_text(row.get_text(" ", strip=True)),
            )
        )
    return events


def fetch_humanities_center(days: int = 30) -> list[Event]:
    del days
    url = "https://shc.stanford.edu/stanford-humanities-center/events"
    events: list[Event] = []
    for page_url, html in _fetch_pages(url):
        events.extend(parse_humanities_center(html, page_url))
    if not events:
        raise RuntimeError("Humanities Center events page: no event rows parsed")
    return events


def parse_gsb(html: str, page_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    for row in soup.select(".view__content-row"):
        link = row.select_one(".title a[href]")
        if link is None:
            continue
        title = link.get_text(" ", strip=True)
        summary_node = row.select_one(".summary")
        summary = summary_node.get_text(" ", strip=True) if summary_node else None
        loc_node = row.select_one(".location-type")
        location = loc_node.get_text(" ", strip=True) if loc_node else None
        blocks = row.select(".split-date-time") or [row]
        for block in blocks:
            date_node = block.select_one(".date")
            time_node = block.select_one(".time")
            if date_node is None:
                continue
            day = date_parser.parse(date_node.get_text(" ", strip=True))
            start_clock, end_clock = clocks_from_text(
                time_node.get_text(" ", strip=True) if time_node else ""
            )
            events.append(
                build_event(
                    title=title,
                    start=at_clock(day, start_clock),
                    end=at_clock(day, end_clock) if end_clock else None,
                    location=location,
                    url=urljoin(page_url, link["href"]),
                    source_name="Stanford GSB",
                    source_url="https://www.gsb.stanford.edu/events",
                    description=summary,
                    audience=classify_audience_from_text(summary, title),
                )
            )
    return events


def fetch_gsb(days: int = 30) -> list[Event]:
    del days
    url = "https://www.gsb.stanford.edu/events"
    events: list[Event] = []
    for page_url, html in _fetch_pages(url):
        events.extend(parse_gsb(html, page_url))
    if not events:
        raise RuntimeError("GSB events page: no event rows parsed")
    return events


_MED_URL = "https://med.stanford.edu/healthlibrary/lectures-events.html"
_MED_STOP = {"let's stay in touch", "stanford health library"}


def parse_health_library(html: str, page_url: str = _MED_URL) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    year = today_pt().year
    capture = False
    events: list[Event] = []
    current_title: str | None = None
    chunks: list = []

    def flush() -> None:
        nonlocal current_title, chunks
        if not current_title:
            chunks = []
            return
        text_bits = [node.get_text("\n", strip=True) for node in chunks]
        blob = "\n".join(text_bits)
        match = _DATE_RE.search(blob)
        if match:
            event_year = int(match.group(3)) if match.group(3) else year
            day = date_parser.parse(f"{match.group(1)} {match.group(2)} {event_year}")
            start_clock, end_clock = clocks_from_text(blob)
            location = None
            for node in chunks:
                if node.name != "p":
                    continue
                if not _DATE_RE.search(node.get_text(" ", strip=True)):
                    continue
                nxt = node.find_next_sibling("p")
                if nxt is not None:
                    location = re.sub(r"\s+", " ", nxt.get_text(", ", strip=True)).strip() or None
                break
            description = None
            for node in chunks:
                if node.name != "p":
                    continue
                paragraph = node.get_text(" ", strip=True)
                if _DATE_RE.search(paragraph):
                    break
                if len(paragraph) > 40:
                    description = paragraph
                    break
            link = None
            for node in chunks:
                anchor = node.find("a", href=True) if hasattr(node, "find") else None
                if anchor and anchor["href"].startswith("http"):
                    link = anchor["href"]
                    break
            events.append(
                build_event(
                    title=current_title,
                    start=at_clock(day, start_clock),
                    end=at_clock(day, end_clock) if end_clock else None,
                    location=location,
                    url=link or page_url,
                    source_name="Stanford Health Library",
                    source_url=_MED_URL,
                    description=description,
                    audience=classify_audience_from_text(blob, current_title),
                )
            )
        current_title = None
        chunks = []

    for node in soup.find_all(["h2", "p"]):
        if node.name == "h2":
            flush()
            heading = node.get_text(" ", strip=True)
            year_match = re.search(r"LECTURES\s*\+\s*EVENTS\s+(20\d{2})", heading, re.I)
            if year_match:
                year = int(year_match.group(1))
                capture = True
                continue
            if not capture:
                continue
            if heading.casefold() in _MED_STOP:
                capture = False
                break
            current_title = heading
            continue
        if capture and current_title:
            chunks.append(node)
    flush()
    return events


def fetch_health_library(days: int = 30) -> list[Event]:
    del days
    html = get(_MED_URL).text
    events = parse_health_library(html)
    if not events:
        # The page is a prose list; zero parsed events means the markup moved.
        raise RuntimeError("Stanford Health Library lectures page: no dated talks parsed")
    return events


_SLAC_URLS = (
    "https://www6.slac.stanford.edu/news-and-events/events/public-lectures",
    "https://www6.slac.stanford.edu/news-and-events/events/seminars-and-conferences",
)


def parse_slac(html: str, page_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    this_year = today_pt().year
    for card in soup.select(".c-card"):
        link = card.select_one("a.c-card__link[href]") or card.select_one(".c-card__title a[href]")
        if link is None:
            continue
        title = link.get_text(" ", strip=True)
        body = card.get_text("\n", strip=True)
        match = _DATE_RE.search(body)
        if not match or not title:
            continue
        year_in_title = re.search(r"(20\d{2})", f"{title} {body}")
        year = int(match.group(3) or (year_in_title.group(1) if year_in_title else this_year))
        day = date_parser.parse(f"{match.group(1)} {match.group(2)} {year}")
        start_clock, end_clock = clocks_from_text(body)
        href = link["href"]
        if href.startswith("#") or "archive" in href:
            continue
        events.append(
            build_event(
                title=title,
                start=at_clock(day, start_clock),
                end=at_clock(day, end_clock) if end_clock else None,
                location=None,
                url=urljoin(page_url, href),
                source_name="SLAC",
                source_url=page_url,
                description=None,
                audience=classify_audience_from_text(body, title),
            )
        )
    return events


def fetch_slac(days: int = 30) -> list[Event]:
    del days
    events: list[Event] = []
    failures: list[Exception] = []
    for url in _SLAC_URLS:
        try:
            html = get(url).text
        except Exception as exc:
            failures.append(exc)
            continue
        events.extend(parse_slac(html, url))
    if not events and len(failures) == len(_SLAC_URLS):
        raise failures[0]
    return events
