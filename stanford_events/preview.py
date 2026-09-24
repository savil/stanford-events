"""Human-readable and HTML previews of normalized events."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Iterable

from .normalize import Event, PT, parse_datetime

_AUDIENCE_LABEL = {
    "open_to_public": "Public",
    "stanford_only": "Stanford only",
    "unknown": "Unknown",
}


def _audience_label(ev: Event) -> str:
    return _AUDIENCE_LABEL.get(ev.get("audience") or "unknown", "Unknown")


def _day_key(ev: Event) -> str:
    dt = parse_datetime(ev.get("start"))
    if dt is None:
        return "Unknown"
    return dt.astimezone(PT).strftime("%Y-%m-%d %A")


def _time_range(ev: Event) -> str:
    start = parse_datetime(ev.get("start"))
    end = parse_datetime(ev.get("end")) if ev.get("end") else None
    if start is None:
        return ""
    start = start.astimezone(PT)
    if start.hour == 0 and start.minute == 0 and end is None:
        return "all day"
    s = start.strftime("%-I:%M %p")
    if end:
        end = end.astimezone(PT)
        s += f" – {end.strftime('%-I:%M %p')}"
    return s + " PT"


def group_by_day(events: Iterable[Event]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        grouped[_day_key(ev)].append(ev)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))


def render_markdown(events: list[Event], *, title: str = "Stanford events preview") -> str:
    lines = [f"# {title}", "", f"_Generated {datetime.now(tz=PT).strftime('%Y-%m-%d %H:%M %Z')}_", ""]
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
            lines.append(f"  - source: {ev['source_name']} · audience: `{ev.get('audience', 'unknown')}` · [link]({ev['url']})")
            if ev.get("description"):
                lines.append(f"  - {ev['description']}")
        lines.append("")
    return "\n".join(lines)


def render_html(events: list[Event], *, title: str = "Stanford events preview") -> str:
    generated = datetime.now(tz=PT).strftime("%Y-%m-%d %H:%M %Z")
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        f"<title>{escape(title)}</title>",
        "<style>",
        "body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:1rem;line-height:1.45;background:#f7f7f8;color:#111}",
        "main{max-width:42rem;margin:0 auto}",
        "h1{font-size:1.35rem;margin:0 0 .25rem}",
        ".meta{color:#555;font-size:.9rem;margin-bottom:1.25rem}",
        "h2{font-size:1.05rem;margin:1.4rem 0 .5rem;padding-bottom:.25rem;border-bottom:1px solid #ddd}",
        "article{background:#fff;border:1px solid #e5e5e7;border-radius:10px;padding:.75rem .9rem;margin:.55rem 0}",
        "article h3{font-size:1rem;margin:0 0 .35rem}",
        ".when,.where,.src{font-size:.88rem;color:#333}",
        ".src a{color:#0b57d0;text-decoration:none}",
        ".desc{font-size:.88rem;color:#444;margin:.4rem 0 0}",
        ".badge{display:inline-block;font-size:.72rem;font-weight:600;letter-spacing:.02em;"
        "padding:.12rem .45rem;border-radius:999px;margin:.15rem 0 .35rem;vertical-align:middle}",
        ".badge-public{background:#e6f4ea;color:#137333}",
        ".badge-stanford{background:#e8f0fe;color:#174ea6}",
        ".badge-unknown{background:#f1f3f4;color:#5f6368}",
        "</style>",
        "</head>",
        "<body><main>",
        f"<h1>{escape(title)}</h1>",
        f'<p class="meta">Generated {escape(generated)} · today..+30 days PT</p>',
    ]
    grouped = group_by_day(events)
    if not grouped:
        parts.append("<p><em>No events in window.</em></p>")
    for day, items in grouped.items():
        parts.append(f"<h2>{escape(day)}</h2>")
        for ev in items:
            aud = ev.get("audience") or "unknown"
            if aud == "open_to_public":
                badge_cls = "badge badge-public"
            elif aud == "stanford_only":
                badge_cls = "badge badge-stanford"
            else:
                badge_cls = "badge badge-unknown"
            parts.append("<article>")
            parts.append(f"<h3>{escape(ev['title'])}</h3>")
            parts.append(
                f'<span class="{badge_cls}">{escape(_audience_label(ev))}</span>'
            )
            parts.append(f'<div class="when">{escape(_time_range(ev))}</div>')
            if ev.get("location"):
                parts.append(f'<div class="where">{escape(ev["location"])}</div>')
            parts.append(
                f'<div class="src">{escape(ev["source_name"])} · '
                f'<a href="{escape(ev["url"], quote=True)}">details</a></div>'
            )
            if ev.get("description"):
                parts.append(f'<p class="desc">{escape(ev["description"])}</p>')
            parts.append("</article>")
    parts.extend(["</main></body></html>", ""])
    return "\n".join(parts)
