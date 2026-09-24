"""Shared event schema, hashing, window filter, and dedupe."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

PT = ZoneInfo("America/Los_Angeles")

Event = dict[str, Any]

Audience = Literal["open_to_public", "stanford_only", "unknown"]
AUDIENCE_VALUES: frozenset[str] = frozenset({"open_to_public", "stanford_only", "unknown"})


def make_id(source_url: str, title: str, start_iso: str) -> str:
    raw = f"{source_url}|{title}|{start_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ensure_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as America/Los_Angeles."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=PT)
    return dt.astimezone(PT)


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    text = str(value).strip()
    if not text:
        return None
    dt = date_parser.parse(text)
    return ensure_aware(dt)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return ensure_aware(dt).isoformat()


def short_description(text: str | None, limit: int = 280) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def normalize_audience(value: str | None) -> Audience:
    if value not in AUDIENCE_VALUES:
        raise ValueError(
            f"audience must be one of {sorted(AUDIENCE_VALUES)}, got {value!r}"
        )
    return value  # type: ignore[return-value]


# Audience-tag names shared by Localist and Drupal calendars.
# A public tag wins. Campus-only tags with no public tag are stanford_only.
# Anything else (including "By Invitation Only") stays unknown.
PUBLIC_AUDIENCE_NAMES = frozenset(
    {
        "everyone",
        "general public",
        "open to the public",
        "open to public",
    }
)
STANFORD_AUDIENCE_NAMES = frozenset(
    {
        "students",
        "students - undergraduates",
        "students - graduates",
        "postdocs",
        "faculty",
        "faculty/staff",
        "staff",
        "staff - academic",
        "staff - managers",
        "affiliates",
        "alumni",
        "alumni/friends",
        "members",
    }
)


def classify_audience_names(names: list[str] | None) -> Audience:
    """Map a list of audience-tag names. Empty or unrecognized → unknown."""
    cleaned = []
    for name in names or []:
        text = str(name).strip().lower()
        if text:
            cleaned.append(text)
    if not cleaned:
        return "unknown"
    lowered = set(cleaned)
    if lowered & PUBLIC_AUDIENCE_NAMES:
        return "open_to_public"
    if lowered <= STANFORD_AUDIENCE_NAMES:
        return "stanford_only"
    return "unknown"


# Text classifiers shared by HTML sources (HAI listing/detail, etc.)
_PUBLIC_RE = re.compile(
    r"(?i)\b(?:"
    r"open\s+to\s+the\s+public|"
    r"open\s+to\s+public|"
    r"open\s+to\s+all(?!\s+stanford)|"
    r"registration\s+open\s+to\s+all|"
    r"general\s+public|"
    r"everyone\s+is\s+welcome|"
    r"free\s+and\s+open\s+to\s+the\s+public|"
    # "free and open to adults/anyone/…" but not "free and open to Stanford…"
    r"free\s+and\s+open\s+to(?!\s+stanford\b|\s+the\s+stanford\b)"
    r")\b"
)
_STANFORD_ONLY_RE = re.compile(
    r"(?i)\b(?:"
    r"open\s+to\s+stanford(?:\s+community)?(?:\s+members)?|"
    r"for\s+the\s+stanford\s+community|"
    r"stanford\s+community\s+members|"
    r"stanford\s+only|"
    r"stanford\s+students\s+only|"
    r"campus\s+only|"
    r"campus\s+community\s+only|"
    r"sunet(?:[- ]id)?(?:\s+required|\s+login)?"
    r")\b"
)


def classify_audience_from_text(*parts: str | None) -> Audience:
    """Prefer clear public / Stanford-only page signals; else unknown.

    Does not invent a default from weak title keywords alone when both sides
    are silent — callers should pass page/listing text first.
    """
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return "unknown"
    # Stanford-only checked first so "Open to Stanford community" wins over
    # looser "open to …" phrasing.
    if _STANFORD_ONLY_RE.search(text):
        return "stanford_only"
    if _PUBLIC_RE.search(text):
        return "open_to_public"
    return "unknown"


def build_event(
    *,
    title: str,
    start: datetime | str,
    end: datetime | str | None = None,
    location: str | None = None,
    url: str,
    source_name: str,
    source_url: str,
    description: str | None = None,
    audience: str,
) -> Event:
    start_dt = parse_datetime(start)
    if start_dt is None:
        raise ValueError(f"missing start for event: {title!r}")
    end_dt = parse_datetime(end) if end else None
    start_iso = to_iso(start_dt)
    assert start_iso is not None
    return {
        "id": make_id(source_url, title.strip(), start_iso),
        "title": title.strip(),
        "start": start_iso,
        "end": to_iso(end_dt) if end_dt else None,
        "location": (location or "").strip() or None,
        "url": url,
        "source_name": source_name,
        "source_url": source_url,
        "description": short_description(description),
        "audience": normalize_audience(audience),
    }


def window_bounds(days: int = 30, now: datetime | None = None) -> tuple[datetime, datetime]:
    now_pt = ensure_aware(now or datetime.now(tz=PT))
    start = datetime.combine(now_pt.date(), datetime.min.time(), tzinfo=PT)
    end = start + timedelta(days=days + 1)  # exclusive end of day+days
    return start, end


def in_window(event: Event, start: datetime, end: datetime) -> bool:
    ev_start = parse_datetime(event.get("start"))
    if ev_start is None:
        return False
    return start <= ev_start < end


def normalize_title(title: str) -> str:
    """Casefold and strip punctuation so near-duplicate titles can be compared."""
    text = unicodedata.normalize("NFKC", title or "").casefold()
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def titles_near(a: str, b: str) -> bool:
    """True when titles are the same phrase, or one adds only a short suffix.

    "Bay Area Tech Economics Seminar" and
    "Bay Area Tech Economics Seminar with Rehan Khan" match.
    A short shared word, or a much longer different title, does not.
    """
    ka, kb = normalize_title(a), normalize_title(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    shorter, longer = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    if len(shorter) < 28 or len(shorter) / len(longer) < 0.62:
        return False
    if not (
        longer.startswith(shorter + " ")
        or longer.endswith(" " + shorter)
        or f" {shorter} " in f" {longer} "
    ):
        return False
    extra = longer.replace(shorter, " ", 1)
    extra_words = [w for w in extra.split() if w]
    return len(extra_words) <= 4


def _clock_is_midnight(dt: datetime) -> bool:
    local = ensure_aware(dt)
    return local.hour == 0 and local.minute == 0 and local.second == 0


def starts_near(a: str | None, b: str | None, *, allow_date_only: bool) -> bool:
    """Same Pacific calendar day and nearly the same clock time.

    When ``allow_date_only`` is set (exact title match), a midnight placeholder
    from a date-only listing matches a timed listing on that day.
    """
    da, db = parse_datetime(a), parse_datetime(b)
    if da is None or db is None:
        return False
    if da.astimezone(PT).date() != db.astimezone(PT).date():
        return False
    if abs((da - db).total_seconds()) <= 15 * 60:
        return True
    if allow_date_only and (_clock_is_midnight(da) or _clock_is_midnight(db)):
        return True
    return False


def _richness(ev: Event) -> tuple:
    start = parse_datetime(ev.get("start"))
    has_clock = 0 if (start is None or _clock_is_midnight(start)) else 1
    audience_known = 0 if (ev.get("audience") or "unknown") == "unknown" else 1
    return (
        audience_known,
        has_clock,
        1 if ev.get("location") else 0,
        1 if ev.get("end") else 0,
        len(ev.get("description") or ""),
    )


def _merge_pair(primary: Event, secondary: Event) -> Event:
    """Keep the richer record and fill gaps from the other source."""
    if _richness(secondary) > _richness(primary):
        primary, secondary = secondary, primary
    merged = dict(primary)
    for field in ("end", "location", "description", "url"):
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]
    if (merged.get("audience") or "unknown") == "unknown" and secondary.get("audience") not in (
        None,
        "unknown",
    ):
        merged["audience"] = secondary["audience"]
    p_start = parse_datetime(merged.get("start"))
    s_start = parse_datetime(secondary.get("start"))
    if (
        p_start
        and s_start
        and _clock_is_midnight(p_start)
        and not _clock_is_midnight(s_start)
    ):
        merged["start"] = secondary["start"]
        if secondary.get("end"):
            merged["end"] = secondary["end"]
    also: list[str] = []
    for name in (
        *(primary.get("also_sources") or []),
        secondary.get("source_name"),
        *(secondary.get("also_sources") or []),
    ):
        if name and name != merged.get("source_name") and name not in also:
            also.append(name)
    if also:
        merged["also_sources"] = also
    else:
        merged.pop("also_sources", None)
    return merged


def dedupe(events: list[Event]) -> list[Event]:
    """Collapse exact ids and near-identical title+start across sources.

    Titles match when they normalize to the same phrase, or one only adds a
    short suffix. Starts match within 15 minutes on the same Pacific day.
    An exact title also matches when one source only stored a date (midnight).
    The kept row prefers a known audience, a real clock time, location, and a
    description; other source names are recorded on ``also_sources``.
    Distinct times on the same day stay separate.
    """
    by_id: dict[str, Event] = {}
    for ev in events:
        prev = by_id.get(ev["id"])
        by_id[ev["id"]] = ev if prev is None else _merge_pair(prev, ev)

    buckets: dict[str, list[Event]] = {}
    for ev in by_id.values():
        dt = parse_datetime(ev.get("start"))
        day = dt.astimezone(PT).date().isoformat() if dt else ""
        buckets.setdefault(day, []).append(ev)

    merged: list[Event] = []
    for group in buckets.values():
        group.sort(key=lambda e: (e.get("start") or "", e.get("title") or "", e.get("source_name") or ""))
        clusters: list[Event] = []
        for ev in group:
            placed = False
            ev_title = ev.get("title") or ""
            for i, canon in enumerate(clusters):
                exact = normalize_title(ev_title) == normalize_title(canon.get("title") or "")
                if titles_near(ev_title, canon.get("title") or "") and starts_near(
                    ev.get("start"), canon.get("start"), allow_date_only=exact
                ):
                    clusters[i] = _merge_pair(canon, ev)
                    placed = True
                    break
            if not placed:
                clusters.append(ev)
        merged.extend(clusters)
    merged.sort(key=lambda e: (e.get("start") or "", e.get("title") or "", e.get("source_name") or ""))
    return merged


def filter_window(events: list[Event], days: int = 30, now: datetime | None = None) -> list[Event]:
    start, end = window_bounds(days=days, now=now)
    return [e for e in events if in_window(e, start, end)]


def iter_window_dates(days: int = 30, now: datetime | None = None) -> list[date]:
    """Inclusive Pacific dates from today through today+``days``."""
    start, end = window_bounds(days=days, now=now)
    dates: list[date] = []
    d = start.date()
    last = (end - timedelta(seconds=1)).date()
    while d <= last:
        dates.append(d)
        d += timedelta(days=1)
    return dates


def today_pt() -> date:
    return datetime.now(tz=PT).date()
