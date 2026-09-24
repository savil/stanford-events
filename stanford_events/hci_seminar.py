"""HCI Seminar HTML table scraper (Fall quarter schedule)."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_util import get
from .normalize import Event, PT, build_event

SOURCE_NAME = "Stanford HCI Seminar"
SOURCE_URL = "https://hci.stanford.edu/seminar/"
DEFAULT_LOCATION = "Gates B3"
START_TIME = (11, 30)  # 11:30am PT
END_TIME = (12, 30)  # 12:30pm PT

# Page states: "Open to the public" / "The seminar is open to the public..."
HCI_AUDIENCE = "open_to_public"


def _parse_row_date(date_text: str, year_hint: int) -> datetime | None:
    """Parse '25 Sep' / '2 Oct' with year from speaker.php?date= or quarter heading."""
    text = date_text.strip()
    if not text:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(f"{text} {year_hint}", fmt)
        except ValueError:
            continue
    return None


def _year_from_heading(soup: BeautifulSoup) -> int | None:
    for tag in soup.find_all(["h1", "h2", "h3"]):
        m = re.search(r"Fall\s+(\d{4})", tag.get_text(" ", strip=True), re.I)
        if m:
            return int(m.group(1))
    return None


def fetch_events() -> list[Event]:
    html = get(SOURCE_URL).text
    soup = BeautifulSoup(html, "lxml")
    year_hint = _year_from_heading(soup) or datetime.now(tz=PT).year

    table = soup.find("table", id="quarter_talk_table") or soup.find("table")
    if table is None:
        raise RuntimeError("HCI seminar page: no schedule table found")

    events: list[Event] = []
    for tr in table.find_all("tr"):
        date_td = tr.find("td", class_="date")
        if date_td is None:
            continue
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        date_text = date_td.get_text(" ", strip=True)
        speaker_td = tr.find("td", class_="speaker")
        speaker = speaker_td.get_text(" ", strip=True) if speaker_td else ""
        speaker_name = ""
        if speaker_td:
            strong = speaker_td.find("strong")
            speaker_name = (
                strong.get_text(strip=True) if strong else speaker.split("\n")[0].strip()
            )

        link = tr.find("a", href=True)
        title = link.get_text(" ", strip=True) if link else ""
        href = link["href"] if link else SOURCE_URL

        # Skip cancelled / no-seminar rows only
        if "no seminar" in f"{speaker_name} {title}".lower():
            continue
        if not date_text:
            continue

        start_date = None
        if link and "date=" in href:
            m = re.search(r"date=(\d{4}-\d{2}-\d{2})", href)
            if m:
                start_date = datetime.strptime(m.group(1), "%Y-%m-%d")
        if start_date is None:
            start_date = _parse_row_date(date_text, year_hint)
        if start_date is None:
            continue

        start = start_date.replace(
            hour=START_TIME[0], minute=START_TIME[1], second=0, microsecond=0, tzinfo=PT
        )
        end = start_date.replace(
            hour=END_TIME[0], minute=END_TIME[1], second=0, microsecond=0, tzinfo=PT
        )

        is_tba_title = (not title) or title.upper() == "TBA"
        is_tba_speaker = (not speaker_name) or speaker_name.upper() == "TBA"
        if is_tba_speaker and is_tba_title:
            display_title = "HCI Seminar (TBA)"
        elif is_tba_title:
            display_title = f"HCI Seminar: {speaker_name}"
        elif is_tba_speaker:
            display_title = title
        else:
            display_title = f"{speaker_name} — {title}"

        abs_url = urljoin(SOURCE_URL, href)
        desc_parts = [
            "Stanford HCI Seminar (CS547)",
            "Fridays 11:30am–12:30pm PT",
            "Open to the public",
        ]
        if speaker:
            desc_parts.insert(1, speaker)

        events.append(
            build_event(
                title=display_title,
                start=start,
                end=end,
                location=DEFAULT_LOCATION,
                url=abs_url,
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                description=" · ".join(desc_parts),
                audience=HCI_AUDIENCE,
            )
        )
    return events
