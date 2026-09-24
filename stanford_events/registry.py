"""Source registry. One entry failing does not fail the others."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import (
    ccrma,
    fsi,
    gse,
    hai,
    hci_seminar,
    hoover,
    html_listings,
    hs_events,
    law_events,
    localist,
    stanford_live,
)
from .normalize import Event
from .sws import fetch_sws

Fetch = Callable[[int], list[Event]]


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    fetch: Fetch


def _days_ignored(fn: Callable[[], list[Event]]) -> Fetch:
    def fetch(days: int = 30) -> list[Event]:
        del days
        return fn()

    return fetch


def _sws(origin: str, source_name: str, source_url: str) -> Fetch:
    def fetch(days: int = 30) -> list[Event]:
        return fetch_sws(
            origin=origin,
            source_name=source_name,
            source_url=source_url,
            days=days,
        )

    return fetch


def _hs(origin: str, source_name: str, source_url: str) -> Fetch:
    def fetch(days: int = 30) -> list[Event]:
        return hs_events.fetch_hs(
            origin=origin,
            source_name=source_name,
            source_url=source_url,
            days=days,
        )

    return fetch


def iter_sources() -> list[Source]:
    return [
        Source("localist", "Localist", localist.fetch_events),
        Source("hci_seminar", "HCI Seminar", _days_ignored(hci_seminar.fetch_events)),
        Source("hai", "HAI", _days_ignored(hai.fetch_events)),
        Source("stanford_live", "Stanford Live", stanford_live.fetch_events),
        Source(
            "siepr",
            "SIEPR",
            _sws("https://siepr.stanford.edu", "SIEPR", "https://siepr.stanford.edu/events"),
        ),
        Source(
            "kipac",
            "KIPAC",
            _sws(
                "https://kipac.stanford.edu",
                "KIPAC",
                "https://kipac.stanford.edu/events/upcoming-events",
            ),
        ),
        Source(
            "qfarm",
            "Q-FARM",
            _sws("https://qfarm.stanford.edu", "Q-FARM", "https://qfarm.stanford.edu/events"),
        ),
        Source(
            "aimi",
            "AIMI",
            _sws(
                "https://aimi.stanford.edu",
                "AIMI",
                "https://aimi.stanford.edu/upcoming-events",
            ),
        ),
        Source(
            "bioengineering",
            "Bioengineering",
            _sws(
                "https://bioengineering.stanford.edu",
                "Bioengineering",
                "https://bioengineering.stanford.edu/events",
            ),
        ),
        Source(
            "statistics",
            "Statistics",
            _hs(
                "https://statistics.stanford.edu",
                "Statistics",
                "https://statistics.stanford.edu/events/statistics-seminar",
            ),
        ),
        Source(
            "psychology",
            "Psychology",
            _hs(
                "https://psychology.stanford.edu",
                "Psychology",
                "https://psychology.stanford.edu/news-events/upcoming-events",
            ),
        ),
        Source(
            "physics",
            "Physics",
            _hs(
                "https://physics.stanford.edu",
                "Physics",
                "https://physics.stanford.edu/news-events/upcoming-events",
            ),
        ),
        Source(
            "art",
            "Art & Art History",
            _hs(
                "https://art.stanford.edu",
                "Art & Art History",
                "https://art.stanford.edu/events/calendar-events-exhibitions",
            ),
        ),
        Source("law", "Stanford Law", law_events.fetch_events),
        Source("fsi", "FSI", fsi.fetch_events),
        Source("gse", "Stanford GSE", gse.fetch_events),
        Source("hoover", "Hoover Institution", hoover.fetch_events),
        Source("ccrma", "CCRMA", ccrma.fetch_events),
        Source("neuroscience", "Wu Tsai Neurosciences", html_listings.fetch_neuroscience),
        Source("humanities_center", "Stanford Humanities Center", html_listings.fetch_humanities_center),
        Source("gsb", "Stanford GSB", html_listings.fetch_gsb),
        Source("health_library", "Stanford Health Library", html_listings.fetch_health_library),
        Source("slac", "SLAC", html_listings.fetch_slac),
    ]
