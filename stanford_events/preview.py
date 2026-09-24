"""By-day markdown review and the public HTML listing."""

from __future__ import annotations

import json
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

# Shown when neither audience toggle is on. Kept in sync with the page script.
_ALL_FILTER_NOTE = "Showing all events. Select Public and/or Stanford only to filter."

# URL parsing runs in the head so cards can hide before first paint.
_FILTER_PARSE_JS = r"""
var FILTER_ORDER = ["public", "stanford"];
var FILTER_MAP = {public: "open_to_public", stanford: "stanford_only"};

function normalizeKeys(keys) {
  var set = {};
  (keys || []).forEach(function (key) { set[key] = true; });
  return FILTER_ORDER.filter(function (key) { return set[key]; });
}

function parseAudienceParam(value) {
  var found = {};
  String(value || "").split(",").forEach(function (part) {
    var key = part.trim().toLowerCase().replace(/[\s-]+/g, "_");
    if (key === "public" || key === "open_to_public") found.public = true;
    else if (key === "stanford" || key === "stanford_only" || key === "stanfordonly") found.stanford = true;
  });
  return FILTER_ORDER.filter(function (key) { return found[key]; });
}

function selectionFromLocation(search, hash) {
  var params = new URLSearchParams(search || "");
  var values = params.getAll("audience");
  if (!values.length && hash && hash.indexOf("audience=") !== -1) {
    var bare = hash.charAt(0) === "#" ? hash.slice(1) : hash;
    values = new URLSearchParams(bare).getAll("audience");
  }
  return parseAudienceParam(values.join(","));
}
"""

# Pure helpers shared by the page script. Includes the head parser so both stay in sync.
_FILTER_LIB_JS = (
    _FILTER_PARSE_JS
    + r"""
var ALL_NOTE = __ALL_NOTE__;

function selectionFromUrl(href) {
  var url = new URL(href);
  return selectionFromLocation(url.search, url.hash);
}

function urlWithSelection(href, selectedKeys) {
  var url = new URL(href);
  var keys = normalizeKeys(selectedKeys);
  if (!keys.length) url.searchParams.delete("audience");
  else url.searchParams.set("audience", keys.join(","));
  if (/^#audience=/.test(url.hash)) url.hash = "";
  var search = url.search.replace(/%2C/gi, ",");
  return url.pathname + search + url.hash;
}

function visibleAudience(audience, selectedKeys) {
  var keys = normalizeKeys(selectedKeys);
  if (!keys.length) return true;
  var value = audience || "unknown";
  for (var i = 0; i < keys.length; i++) {
    if (FILTER_MAP[keys[i]] === value) return true;
  }
  return false;
}

function countLabel(n) {
  if (n === 0) return "No events";
  if (n === 1) return "1 event";
  return n + " events";
}

function totalLabel(visible, total, filtering) {
  if (!filtering) return total === 1 ? "1 event." : total + " events.";
  return visible + " of " + total + (total === 1 ? " event." : " events.");
}

function filterNote(selectedKeys, visible, total) {
  var keys = normalizeKeys(selectedKeys);
  if (!keys.length) return ALL_NOTE;
  var names = [];
  if (keys.indexOf("public") !== -1) names.push("Public");
  if (keys.indexOf("stanford") !== -1) names.push("Stanford only");
  var summary = totalLabel(visible, total, true).replace(/\.$/, "");
  return "Showing " + summary + " — " + names.join(" and ") + ".";
}

function filterState(events, allDays, selectedKeys) {
  var keys = normalizeKeys(selectedKeys);
  var filtering = keys.length > 0;
  var visibleByDay = {};
  (allDays || []).forEach(function (day) { visibleByDay[day] = 0; });
  var visible = 0;
  var rows = (events || []).map(function (ev) {
    var show = visibleAudience(ev.audience, keys);
    if (show) {
      visible += 1;
      if (ev.day) visibleByDay[ev.day] = (visibleByDay[ev.day] || 0) + 1;
    }
    return show;
  });
  var days = {};
  (allDays || []).forEach(function (day) {
    var n = visibleByDay[day] || 0;
    days[day] = {
      count: n,
      label: countLabel(n),
      hidden: filtering && n === 0,
      jumpHidden: filtering && n === 0,
      empty: n === 0
    };
  });
  return {
    rows: rows,
    visible: visible,
    total: (events || []).length,
    filtering: filtering,
    keys: keys,
    totalLabel: totalLabel(visible, (events || []).length, filtering),
    note: filterNote(keys, visible, (events || []).length),
    showEmpty: filtering && visible === 0 && (events || []).length > 0,
    days: days
  };
}
""".replace("__ALL_NOTE__", json.dumps(_ALL_FILTER_NOTE))
)

_FILTER_BOOTSTRAP_JS = (
    "(function () {\n"
    + _FILTER_PARSE_JS
    + """
  var keys = selectionFromLocation(location.search, location.hash);
  document.documentElement.setAttribute(
    "data-audience-filter",
    keys.length ? keys.join(",") : "all"
  );
})();
"""
)

_FILTER_DOM_JS = (
    "(function () {\n"
    + _FILTER_LIB_JS
    + """
  function applyFilter(selectedKeys) {
    var keys = normalizeKeys(selectedKeys);
    document.documentElement.setAttribute(
      "data-audience-filter",
      keys.length ? keys.join(",") : "all"
    );
    var events = [];
    Array.prototype.forEach.call(document.querySelectorAll("li[data-audience]"), function (li) {
      events.push({
        audience: li.getAttribute("data-audience"),
        day: li.getAttribute("data-day")
      });
    });
    var allDays = [];
    var sections = document.querySelectorAll("section.day");
    Array.prototype.forEach.call(sections, function (section) {
      allDays.push(section.getAttribute("data-day"));
    });
    var state = filterState(events, allDays, keys);
    Array.prototype.forEach.call(sections, function (section) {
      var day = section.getAttribute("data-day");
      var info = state.days[day];
      if (!info) return;
      section.hidden = info.hidden;
      var countEl = section.querySelector(".count");
      if (countEl) countEl.textContent = info.label;
      var link = document.querySelector('.jump a[href="#d-' + day + '"]');
      if (link) {
        link.hidden = info.jumpHidden;
        link.classList.toggle("is-empty", info.empty);
      }
    });
    var totalEl = document.getElementById("event-total");
    if (totalEl) totalEl.textContent = state.totalLabel;
    var note = document.getElementById("filter-note");
    if (note) note.textContent = state.note;
    var empty = document.getElementById("filter-empty");
    if (empty) empty.hidden = !state.showEmpty;
    Array.prototype.forEach.call(document.querySelectorAll("[data-filter]"), function (btn) {
      var on = keys.indexOf(btn.getAttribute("data-filter")) !== -1;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function keysFromButtons() {
    var keys = [];
    Array.prototype.forEach.call(document.querySelectorAll("[data-filter]"), function (btn) {
      if (btn.getAttribute("aria-pressed") === "true") keys.push(btn.getAttribute("data-filter"));
    });
    return normalizeKeys(keys);
  }

  function writeUrl(keys, mode) {
    var next = urlWithSelection(location.href, keys);
    if (next === location.pathname + location.search + location.hash) return;
    try {
      if (mode === "push") history.pushState(null, "", next);
      else history.replaceState(null, "", next);
    } catch (err) {
      // file:// documents can reject history updates. Filtering still applies.
    }
  }

  globalThis.StanfordEventsFilter = {
    parseAudienceParam: parseAudienceParam,
    selectionFromLocation: selectionFromLocation,
    selectionFromUrl: selectionFromUrl,
    urlWithSelection: urlWithSelection,
    visibleAudience: visibleAudience,
    filterState: filterState,
    countLabel: countLabel,
    totalLabel: totalLabel,
    filterNote: filterNote,
    normalizeKeys: normalizeKeys
  };

  if (typeof document === "undefined") return;

  var initial = selectionFromUrl(location.href);
  applyFilter(initial);
  writeUrl(initial, "replace");
  Array.prototype.forEach.call(document.querySelectorAll("[data-filter]"), function (btn) {
    btn.addEventListener("click", function () {
      var pressed = btn.getAttribute("aria-pressed") === "true";
      btn.setAttribute("aria-pressed", pressed ? "false" : "true");
      var keys = keysFromButtons();
      applyFilter(keys);
      writeUrl(keys, "push");
    });
  });
  window.addEventListener("popstate", function () {
    applyFilter(selectionFromUrl(location.href));
  });
})();
"""
)

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
a:focus-visible, button:focus-visible {
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
  align-items: center;
  gap: .65rem;
  margin-top: .85rem;
  font-family: system-ui, -apple-system, sans-serif;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: .65rem;
}
.filter-note {
  margin: .55rem 0 0;
  max-width: 40rem;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: .8rem;
  color: var(--muted);
}
.filter-empty { margin-top: 1.2rem; }
[hidden] { display: none !important; }
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
button.filter {
  appearance: none;
  -webkit-appearance: none;
  margin: 0;
  border: 0;
  cursor: pointer;
  padding: .32rem .72rem;
}
button.filter:hover { opacity: .86; }
button.filter[aria-pressed="true"],
button.filter[aria-pressed="true"]:hover,
html[data-audience-filter="public"] button[data-filter="public"],
html[data-audience-filter="stanford"] button[data-filter="stanford"],
html[data-audience-filter="public,stanford"] button[data-filter] {
  opacity: 1;
  box-shadow: 0 0 0 2px var(--accent);
}
html[data-audience-filter="public"] .legend .badge-unknown,
html[data-audience-filter="stanford"] .legend .badge-unknown,
html[data-audience-filter="public,stanford"] .legend .badge-unknown {
  opacity: .45;
}
html[data-audience-filter="public"] li[data-audience]:not([data-audience="open_to_public"]),
html[data-audience-filter="stanford"] li[data-audience]:not([data-audience="stanford_only"]),
html[data-audience-filter="public,stanford"] li[data-audience]:not([data-audience="open_to_public"]):not([data-audience="stanford_only"]) {
  display: none !important;
}
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
        f'<script id="audience-filter-bootstrap">{_FILTER_BOOTSTRAP_JS}</script>',
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
        f'<li><strong id="event-total">{escape(count_label)}.</strong></li>',
        f"<li><strong>Updated</strong> {escape(_fmt_stamp(generated_at))}</li>",
        "</ul>",
        '<div class="legend">',
        '<div class="filters" role="group" aria-label="Filter by audience" aria-controls="calendar">',
        '<button type="button" class="badge badge-public filter" data-filter="public" aria-pressed="false">Public</button>',
        '<button type="button" class="badge badge-stanford filter" data-filter="stanford" aria-pressed="false">Stanford only</button>',
        "</div>",
        '<span class="badge badge-unknown">Unknown</span>',
        "</div>",
        f'<p class="filter-note" id="filter-note" aria-live="polite">{escape(_ALL_FILTER_NOTE)}</p>',
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
    parts.append('<main id="calendar">')
    parts.append(
        '<p id="filter-empty" class="empty-day filter-empty wrap" hidden>'
        "No events match this filter.</p>"
    )

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
        parts.append(
            f'<section class="day wrap" id="d-{d.isoformat()}" data-day="{d.isoformat()}">'
        )
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
            parts.append(
                f'<li data-audience="{escape(aud)}" data-day="{d.isoformat()}">'
            )
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
            "<p>Calendars include Stanford Events (Localist) plus school, venue, and "
            "seminar pages. A source that fails is noted above and the rest are still listed.</p>",
            '<p>Times are Pacific (<code>America/Los_Angeles</code>). '
            'Machine-readable copy: <a href="events.json">events.json</a>.</p>',
            "<p>Not an official Stanford University site.</p>",
            "</div></footer>",
            '<script id="audience-filter">',
            _FILTER_DOM_JS,
            "</script>",
            "</body></html>",
            "",
        ]
    )
    return "\n".join(parts)
