"""By-day markdown review and the public HTML listing."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from html import escape
from typing import Iterable

from .normalize import Event, PT, iter_window_dates, parse_datetime

_AUDIENCE_LABEL = {
    "open_to_public": "Public",
    "stanford_only": "Stanford only",
    "unknown": "Unknown",
}

_BADGE_CLASS = {
    "open_to_public": "badge badge-public",
    "stanford_only": "badge badge-stanford",
    "unknown": "badge badge-unknown",
}

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #f4f1ec;
  --ink: #1f1a17;
  --muted: #5e564f;
  --line: #e3dbd2;
  --card: #fffcf9;
  --accent: #8c1515;
  --accent-ink: #6d1212;
  --public-bg: #d9f3e3;
  --public-fg: #08522a;
  --stanford-bg: #dce7fb;
  --stanford-fg: #14367d;
  --unknown-bg: #ece7e2;
  --unknown-fg: #3c362f;
  --warn-bg: #fff4e5;
  --warn-fg: #6a3d09;
  --warn-line: #f0d7b0;
  --max: 46rem;
  --shadow: 0 1px 2px rgba(60, 36, 16, 0.05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141210;
    --ink: #f6f1ea;
    --muted: #c4b8ae;
    --line: #3a332d;
    --card: #221e1b;
    --accent: #f0a3a3;
    --accent-ink: #ffc7c7;
    --public-bg: #143526;
    --public-fg: #c6f5d6;
    --stanford-bg: #1a2d52;
    --stanford-fg: #d4e2ff;
    --unknown-bg: #2c2825;
    --unknown-fg: #e4dbd3;
    --warn-bg: #3a2a14;
    --warn-fg: #ffe3b8;
    --warn-line: #6a4e28;
    --shadow: none;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.45;
}
a { color: inherit; }
a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.wrap { max-width: var(--max); margin: 0 auto; padding: 0 1rem; }
.site-header { padding: 1.6rem 0 1rem; }
.eyebrow {
  margin: 0 0 .2rem;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--accent);
}
h1 { margin: 0; font-size: 2rem; font-weight: 600; letter-spacing: -0.02em; }
.lede { margin: .55rem 0 0; color: var(--muted); font-size: 1.02rem; }
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem .9rem;
  margin: .9rem 0 0;
  padding: 0;
  list-style: none;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .86rem;
  color: var(--muted);
}
.stats strong { color: var(--ink); font-weight: 600; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
  margin-top: .85rem;
  font-family: system-ui, -apple-system, sans-serif;
}
.warn {
  margin: .9rem 0 0;
  padding: .7rem .8rem;
  background: var(--warn-bg);
  color: var(--warn-fg);
  border: 1px solid var(--warn-line);
  border-radius: 12px;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .88rem;
}
.jump {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
}
.jump-row {
  display: flex;
  gap: .4rem;
  overflow-x: auto;
  padding: .55rem 0 .65rem;
  scrollbar-width: thin;
}
.jump a {
  flex: 0 0 auto;
  text-decoration: none;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .78rem;
  font-weight: 600;
  color: var(--ink);
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: .32rem .62rem;
}
.jump a.is-empty { color: var(--muted); }
.jump a.is-today, .today-pill {
  background: #8c1515;
  color: #fff;
  border-color: #8c1515;
}
.day { margin: 1.6rem 0 0; scroll-margin-top: 3.6rem; }
.day h2 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .35rem .6rem;
  margin: 0 0 .65rem;
  font-size: 1.18rem;
  font-weight: 600;
}
.day h2 .count {
  margin-left: auto;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .78rem;
  font-weight: 600;
  color: var(--muted);
}
.today-pill {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: .12rem .45rem;
}
.empty-day {
  margin: 0;
  color: var(--muted);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .92rem;
}
.events { list-style: none; margin: 0; padding: 0; display: grid; gap: .55rem; }
.event {
  display: grid;
  grid-template-columns: 1fr;
  gap: .25rem .85rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: .8rem .9rem .85rem;
}
.when {
  font-family: system-ui, -apple-system, sans-serif;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: .92rem;
  color: var(--accent-ink);
}
.event h3 { margin: .15rem 0 0; font-size: 1.05rem; font-weight: 600; line-height: 1.3; }
.event h3 a { text-decoration: none; }
.event h3 a:hover { text-decoration: underline; }
.go { font-family: system-ui, sans-serif; font-size: .85em; }
.where, .src {
  margin: .2rem 0 0;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .86rem;
  color: var(--muted);
}
.badge {
  display: inline-block;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .01em;
  padding: .12rem .48rem;
  border-radius: 999px;
  vertical-align: middle;
}
.badge-public { background: var(--public-bg); color: var(--public-fg); }
.badge-stanford { background: var(--stanford-bg); color: var(--stanford-fg); }
.badge-unknown { background: var(--unknown-bg); color: var(--unknown-fg); }
.site-footer {
  margin: 2rem 0 0;
  padding: 1.2rem 0 2rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .86rem;
}
.site-footer a { color: var(--accent-ink); }
@media (min-width: 640px) {
  h1 { font-size: 2.35rem; }
  .event { grid-template-columns: 7.6rem 1fr; align-items: start; }
  .when { padding-top: .15rem; }
}
@media print {
  .jump { display: none; }
  body { background: #fff; }
  .event { break-inside: avoid; box-shadow: none; }
}
"""


def _audience_label(ev: Event) -> str:
    return _AUDIENCE_LABEL.get(ev.get("audience") or "unknown", "Unknown")


def _fmt_clock(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {suffix}"


def _fmt_stamp(dt: datetime) -> str:
    local = dt.astimezone(PT)
    return f"{local.strftime('%b')} {local.day}, {local.year}, {_fmt_clock(local)} PT"


def _is_all_day(start: datetime, end: datetime | None) -> bool:
    start = start.astimezone(PT)
    if not (start.hour == 0 and start.minute == 0):
        return False
    if end is None:
        return True
    end = end.astimezone(PT)
    if end.date() == start.date() and end.hour == 23 and end.minute >= 59:
        return True
    return False


def _time_range(ev: Event) -> str:
    start = parse_datetime(ev.get("start"))
    end = parse_datetime(ev.get("end")) if ev.get("end") else None
    if start is None:
        return ""
    start = start.astimezone(PT)
    if _is_all_day(start, end):
        return "All day"
    text = _fmt_clock(start)
    if end:
        text += f" – {_fmt_clock(end.astimezone(PT))}"
    return text


def _day_key(ev: Event) -> str:
    dt = parse_datetime(ev.get("start"))
    if dt is None:
        return "Unknown"
    return dt.astimezone(PT).strftime("%Y-%m-%d %A")


def group_by_day(events: Iterable[Event]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        grouped[_day_key(ev)].append(ev)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))


def render_markdown(events: list[Event], *, title: str = "Stanford events") -> str:
    lines = [
        f"# {title}",
        "",
        f"_Generated {datetime.now(tz=PT).strftime('%Y-%m-%d %H:%M %Z')}_",
        "",
    ]
    grouped = group_by_day(events)
    if not grouped:
        lines.append("_No events in window._")
        return "\n".join(lines) + "\n"
    for day, items in grouped.items():
        lines.append(f"## {day}")
        lines.append("")
        for ev in items:
            loc = f" @ {ev['location']}" if ev.get("location") else ""
            aud = _audience_label(ev)
            lines.append(f"- **{ev['title']}** — {_time_range(ev)}{loc} · _{aud}_")
            also = ev.get("also_sources") or []
            also_bit = f" · also {', '.join(also)}" if also else ""
            lines.append(
                f"  - source: {ev['source_name']}{also_bit} · "
                f"audience: `{ev.get('audience', 'unknown')}` · [link]({ev['url']})"
            )
            if ev.get("description"):
                lines.append(f"  - {ev['description']}")
        lines.append("")
    return "\n".join(lines)


def _events_by_date(events: Iterable[Event]) -> dict[date, list[Event]]:
    grouped: dict[date, list[Event]] = defaultdict(list)
    for ev in events:
        dt = parse_datetime(ev.get("start"))
        if dt is None:
            continue
        grouped[dt.astimezone(PT).date()].append(ev)
    for items in grouped.values():
        items.sort(key=lambda e: (e.get("start") or "", e.get("title") or ""))
    return grouped


def _error_lines(errors: list[dict] | None) -> list[str]:
    lines: list[str] = []
    for err in errors or []:
        source = str(err.get("source") or "unknown source")
        message = str(err.get("error") or "failed").replace("\n", " ").strip()
        if len(message) > 180:
            message = message[:179].rstrip() + "…"
        lines.append(f"{source}: {message}")
    return lines


def render_html(
    events: list[Event],
    *,
    title: str = "Stanford events",
    errors: list[dict] | None = None,
    days: int = 30,
    now: datetime | None = None,
) -> str:
    """Public by-day page for today through +``days`` in America/Los_Angeles."""
    generated_at = now or datetime.now(tz=PT)
    window = iter_window_dates(days=days, now=generated_at)
    by_date = _events_by_date(events)
    shown = [ev for d in window for ev in by_date.get(d, [])]
    first, last = window[0], window[-1]
    window_label = (
        f"{first.strftime('%b')} {first.day} – {last.strftime('%b')} {last.day}, {last.year}"
    )
    error_lines = _error_lines(errors)
    count_label = f"{len(shown)} event" if len(shown) == 1 else f"{len(shown)} events"

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        '<meta name="description" content="Stanford campus events for the next 30 days, listed by day."/>',
        '<link rel="canonical" href="https://savil.github.io/stanford-events/"/>',
        f"<title>{escape(title)}</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head>",
        "<body>",
        '<header class="site-header"><div class="wrap">',
        '<p class="eyebrow">Unofficial listing</p>',
        f"<h1>{escape(title)}</h1>",
        '<p class="lede">Campus events from today through the next 30 days, Pacific time. '
        "Every event from the current sources is listed.</p>",
        '<ul class="stats">',
        f"<li><strong>Window.</strong> {escape(window_label)}</li>",
        f"<li><strong>{escape(count_label)}.</strong></li>",
        f"<li><strong>Updated</strong> {escape(_fmt_stamp(generated_at))}</li>",
        "</ul>",
        '<div class="legend" aria-label="Audience">',
        '<span class="badge badge-public">Public</span>',
        '<span class="badge badge-stanford">Stanford only</span>',
        '<span class="badge badge-unknown">Unknown</span>',
        "</div>",
    ]
    if error_lines:
        parts.append(
            '<p class="warn"><strong>Some sources did not refresh.</strong> '
            + escape(" ".join(error_lines))
            + " Events from the sources that succeeded are still listed.</p>"
        )
    parts.extend(
        [
            "</div></header>",
            '<nav class="jump" aria-label="Days"><div class="wrap jump-row">',
        ]
    )
    today = generated_at.astimezone(PT).date()
    for d in window:
        classes = []
        if d == today:
            classes.append("is-today")
        if not by_date.get(d):
            classes.append("is-empty")
        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        chip = f"{d.strftime('%b')} {d.day}"
        parts.append(f'<a{class_attr} href="#d-{d.isoformat()}">{escape(chip)}</a>')
    parts.append("</div></nav>")
    parts.append("<main>")

    if not shown:
        parts.append('<div class="wrap"><p class="empty-day">No events in this window.</p></div>')

    for d in window:
        items = by_date.get(d, [])
        n = len(items)
        if n == 0:
            count = "No events"
        elif n == 1:
            count = "1 event"
        else:
            count = f"{n} events"
        heading = f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}"
        parts.append(f'<section class="day wrap" id="d-{d.isoformat()}">')
        parts.append("<h2>")
        parts.append(f'<span class="name">{escape(heading)}</span>')
        if d == today:
            parts.append('<span class="today-pill">Today</span>')
        parts.append(f'<span class="count">{escape(count)}</span>')
        parts.append("</h2>")
        if not items:
            parts.append('<p class="empty-day">Nothing listed.</p>')
            parts.append("</section>")
            continue
        parts.append('<ol class="events">')
        for ev in items:
            aud = ev.get("audience") or "unknown"
            badge_cls = _BADGE_CLASS.get(aud, "badge badge-unknown")
            url = escape(ev.get("url") or "", quote=True)
            also = ev.get("also_sources") or []
            source = ev.get("source_name") or ""
            if also:
                source_line = f"{source} · also {', '.join(also)}"
            else:
                source_line = source
            parts.append("<li>")
            parts.append('<article class="event">')
            parts.append(f'<div class="when">{escape(_time_range(ev))}</div>')
            parts.append("<div>")
            parts.append(
                f'<span class="{badge_cls}" data-audience="{escape(aud)}">'
                f"{escape(_audience_label(ev))}</span>"
            )
            parts.append(
                f'<h3><a href="{url}">{escape(ev.get("title") or "")} '
                f'<span class="go" aria-hidden="true">↗</span></a></h3>'
            )
            if ev.get("location"):
                parts.append(f'<p class="where">{escape(ev["location"])}</p>')
            parts.append(f'<p class="src">{escape(source_line)}</p>')
            parts.append("</div></article></li>")
        parts.append("</ol></section>")

    parts.extend(
        [
            "</main>",
            '<footer class="site-footer"><div class="wrap">',
            "<p>Sources in this version: Stanford Events (including Bing Concert Hall), "
            "the HCI Seminar, and Stanford HAI. More sources come later.</p>",
            '<p>Times are Pacific (<code>America/Los_Angeles</code>). '
            'Machine-readable copy: <a href="events.json">events.json</a>.</p>',
            "<p>Not an official Stanford University site.</p>",
            "</div></footer>",
            "</body></html>",
            "",
        ]
    )
    return "\n".join(parts)
