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
    # source_name values this fetch writes. Used to reuse the previous listing
    # when the fetch fails. Empty means there is nothing to reuse.
    source_names: tuple[str, ...] = ()


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


def _sws_source(key: str, label: str, origin: str, source_name: str, source_url: str) -> Source:
    return Source(
        key,
        label,
        _sws(origin, source_name, source_url),
        source_names=(source_name,),
    )


def _hs_source(key: str, label: str, origin: str, source_name: str, source_url: str) -> Source:
    return Source(
        key,
        label,
        _hs(origin, source_name, source_url),
        source_names=(source_name,),
    )


def iter_sources() -> list[Source]:
    return [
        Source(
            "localist",
            "Localist",
            localist.fetch_events,
            source_names=(localist.SOURCE_NAME, localist.BING_SOURCE_NAME),
        ),
        Source(
            "hci_seminar",
            "HCI Seminar",
            _days_ignored(hci_seminar.fetch_events),
            source_names=(hci_seminar.SOURCE_NAME,),
        ),
        Source(
            "hai",
            "HAI",
            _days_ignored(hai.fetch_events),
            source_names=(hai.SOURCE_NAME,),
        ),
        Source(
            "stanford_live",
            "Stanford Live",
            stanford_live.fetch_events,
            source_names=(stanford_live.SOURCE_NAME,),
        ),
        _sws_source(
            "siepr",
            "SIEPR",
            "https://siepr.stanford.edu",
            "SIEPR",
            "https://siepr.stanford.edu/events",
        ),
        _sws_source(
            "kipac",
            "KIPAC",
            "https://kipac.stanford.edu",
            "KIPAC",
            "https://kipac.stanford.edu/events/upcoming-events",
        ),
        _sws_source(
            "qfarm",
            "Q-FARM",
            "https://qfarm.stanford.edu",
            "Q-FARM",
            "https://qfarm.stanford.edu/events",
        ),
        _sws_source(
            "aimi",
            "AIMI",
            "https://aimi.stanford.edu",
            "AIMI",
            "https://aimi.stanford.edu/upcoming-events",
        ),
        _sws_source(
            "bioengineering",
            "Bioengineering",
            "https://bioengineering.stanford.edu",
            "Bioengineering",
            "https://bioengineering.stanford.edu/events",
        ),
        _hs_source(
            "statistics",
            "Statistics",
            "https://statistics.stanford.edu",
            "Statistics",
            "https://statistics.stanford.edu/events/statistics-seminar",
        ),
        _hs_source(
            "psychology",
            "Psychology",
            "https://psychology.stanford.edu",
            "Psychology",
            "https://psychology.stanford.edu/news-events/upcoming-events",
        ),
        _hs_source(
            "physics",
            "Physics",
            "https://physics.stanford.edu",
            "Physics",
            "https://physics.stanford.edu/news-events/upcoming-events",
        ),
        _hs_source(
            "art",
            "Art & Art History",
            "https://art.stanford.edu",
            "Art & Art History",
            "https://art.stanford.edu/events/calendar-events-exhibitions",
        ),
        Source(
            "law",
            "Stanford Law",
            law_events.fetch_events,
            source_names=(law_events.SOURCE_NAME,),
        ),
        Source("fsi", "FSI", fsi.fetch_events, source_names=(fsi.SOURCE_NAME,)),
        Source("gse", "Stanford GSE", gse.fetch_events, source_names=(gse.SOURCE_NAME,)),
        Source(
            "hoover",
            "Hoover Institution",
            hoover.fetch_events,
            source_names=(hoover.SOURCE_NAME,),
        ),
        Source("ccrma", "CCRMA", ccrma.fetch_events, source_names=(ccrma.SOURCE_NAME,)),
        Source(
            "neuroscience",
            "Wu Tsai Neurosciences",
            html_listings.fetch_neuroscience,
            source_names=(html_listings.NEUROSCIENCE_SOURCE_NAME,),
        ),
        Source(
            "humanities_center",
            "Stanford Humanities Center",
            html_listings.fetch_humanities_center,
            source_names=(html_listings.HUMANITIES_SOURCE_NAME,),
        ),
        Source(
            "gsb",
            "Stanford GSB",
            html_listings.fetch_gsb,
            source_names=(html_listings.GSB_SOURCE_NAME,),
        ),
        Source(
            "health_library",
            "Stanford Health Library",
            html_listings.fetch_health_library,
            source_names=(html_listings.HEALTH_LIBRARY_SOURCE_NAME,),
        ),
        Source(
            "slac",
            "SLAC",
            html_listings.fetch_slac,
            source_names=(html_listings.SLAC_SOURCE_NAME,),
        ),
    ]
