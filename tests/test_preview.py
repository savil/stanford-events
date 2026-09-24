"""Public by-day HTML page."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from stanford_events.normalize import build_event
from stanford_events.preview import render_html

PT = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 24, 9, 0, tzinfo=PT)


def _ev(**kwargs):
    defaults = dict(
        title="Library hours",
        start=datetime(2026, 9, 24, 9, 0, tzinfo=PT),
        url="https://events.stanford.edu/event/library",
        source_name="Stanford Events (Localist)",
        source_url="https://events.stanford.edu/",
        audience="open_to_public",
        location="Green Library",
    )
    defaults.update(kwargs)
    return build_event(**defaults)


class PreviewTests(unittest.TestCase):
    def test_by_day_page_shows_required_fields(self):
        events = [
            _ev(),
            _ev(
                title="Faculty meeting",
                start=datetime(2026, 9, 25, 0, 0, tzinfo=PT),
                audience="stanford_only",
                location=None,
                url="https://events.stanford.edu/event/faculty",
            ),
            _ev(
                title="Untitled workshop",
                start=datetime(2026, 9, 26, 14, 0, tzinfo=PT),
                audience="unknown",
                url="https://hai.stanford.edu/events/workshop",
                source_name="Stanford HAI",
                source_url="https://hai.stanford.edu/events",
            ),
        ]
        events[2]["also_sources"] = ["Stanford Events (Localist)"]
        html = render_html(
            events,
            errors=[{"source": "hci_seminar", "error": "RuntimeError: timeout"}],
            now=NOW,
            days=30,
        )
        self.assertIn("Thursday, September 24", html)
        self.assertIn("Today", html)
        self.assertIn("9:00 AM", html)
        self.assertIn("All day", html)
        self.assertIn("Library hours", html)
        self.assertIn("Green Library", html)
        self.assertIn("Stanford Events (Localist)", html)
        self.assertIn('data-audience="open_to_public"', html)
        self.assertIn(">Public<", html)
        self.assertIn(">Stanford only<", html)
        self.assertIn(">Unknown<", html)
        self.assertIn("https://events.stanford.edu/event/library", html)
        self.assertIn("also Stanford Events (Localist)", html)
        self.assertIn("hci_seminar: RuntimeError: timeout", html)
        self.assertIn('id="d-2026-09-24"', html)
        self.assertIn('id="d-2026-10-24"', html)
        self.assertNotIn("<select", html)
        self.assertNotIn('type="search"', html)
        self.assertNotIn("traceback", html.lower())

    def test_empty_window(self):
        html = render_html([], now=NOW, days=30)
        self.assertIn("No events in this window.", html)
        self.assertIn("Nothing listed.", html)
        self.assertIn('id="filter-empty"', html)


def _script(html: str, script_id: str) -> str:
    open_tag = f'<script id="{script_id}">'
    start = html.index(open_tag) + len(open_tag)
    end = html.index("</script>", start)
    return html[start:end]


def _node(source: str) -> str:
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is required to run the audience filter script")
    proc = subprocess.run(
        [node, "-e", source],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout


class AudienceFilterTests(unittest.TestCase):
    def test_page_embeds_filter_controls(self):
        html = render_html(
            [
                _ev(),
                _ev(
                    title="Faculty meeting",
                    start=datetime(2026, 9, 25, 11, 0, tzinfo=PT),
                    audience="stanford_only",
                    url="https://events.stanford.edu/event/faculty",
                ),
                _ev(
                    title="Mystery talk",
                    start=datetime(2026, 9, 26, 15, 0, tzinfo=PT),
                    audience="unknown",
                    url="https://hai.stanford.edu/events/mystery",
                ),
            ],
            now=NOW,
        )
        self.assertIn('role="group"', html)
        self.assertIn('aria-label="Filter by audience"', html)
        self.assertIn('data-filter="public"', html)
        self.assertIn('data-filter="stanford"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn(">Public</button>", html)
        self.assertIn(">Stanford only</button>", html)
        self.assertIn('id="event-total"', html)
        self.assertIn('id="filter-note"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('data-audience="open_to_public" data-day="2026-09-24"', html)
        self.assertIn('data-day="2026-09-25"', html)
        self.assertIn('id="audience-filter"', html)
        self.assertIn('id="audience-filter-bootstrap"', html)
        self.assertIn('html[data-audience-filter="public"]', html)
        self.assertIn('html[data-audience-filter="stanford"]', html)
        self.assertIn('html[data-audience-filter="public,stanford"]', html)
        self.assertNotIn("<select", html)
        self.assertNotIn('type="search"', html)

    def test_filter_predicate_show_hide_and_url(self):
        html = render_html([_ev()], now=NOW)
        script = _script(html, "audience-filter")
        cases = {
            "events": [
                {"audience": "open_to_public", "day": "2026-09-24"},
                {"audience": "stanford_only", "day": "2026-09-24"},
                {"audience": "unknown", "day": "2026-09-25"},
                {"audience": "open_to_public", "day": "2026-09-26"},
            ],
            "days": ["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"],
        }
        source = (
            script
            + "\nconst assert = require('node:assert');\n"
            + "const F = globalThis.StanfordEventsFilter;\n"
            + "const cases = "
            + json.dumps(cases)
            + ";\n"
            + r"""
assert.deepEqual(F.parseAudienceParam(""), []);
assert.deepEqual(F.parseAudienceParam("unknown"), []);
assert.deepEqual(F.parseAudienceParam("public,stanford"), ["public", "stanford"]);
assert.deepEqual(F.parseAudienceParam("open_to_public"), ["public"]);
assert.deepEqual(F.parseAudienceParam("Stanford-Only"), ["stanford"]);
assert.deepEqual(
  F.selectionFromLocation("?audience=public&audience=stanford", "#d-2026-09-24"),
  ["public", "stanford"]
);
assert.deepEqual(F.selectionFromLocation("", "#d-2026-09-24"), []);
assert.deepEqual(
  F.selectionFromLocation("?audience=public", "#audience=stanford"),
  ["public"]
);
assert.deepEqual(F.selectionFromLocation("", "#audience=stanford"), ["stanford"]);

const page = "https://savil.github.io/stanford-events/?audience=public#d-2026-09-24";
assert.deepEqual(F.selectionFromUrl(page), ["public"]);
assert.equal(
  F.urlWithSelection(page, ["public"]),
  "/stanford-events/?audience=public#d-2026-09-24"
);
assert.equal(
  F.urlWithSelection(page, []),
  "/stanford-events/#d-2026-09-24"
);
assert.equal(
  F.urlWithSelection("https://savil.github.io/stanford-events/#audience=stanford", ["stanford"]),
  "/stanford-events/?audience=stanford"
);
assert.equal(
  F.urlWithSelection("https://savil.github.io/stanford-events/", ["stanford", "public"]),
  "/stanford-events/?audience=public,stanford"
);

assert.equal(F.visibleAudience("unknown", []), true);
assert.equal(F.visibleAudience("unknown", ["public"]), false);
assert.equal(F.visibleAudience("unknown", ["stanford"]), false);
assert.equal(F.visibleAudience("unknown", ["public", "stanford"]), false);
assert.equal(F.visibleAudience("open_to_public", ["public"]), true);
assert.equal(F.visibleAudience("open_to_public", ["stanford"]), false);
assert.equal(F.visibleAudience("stanford_only", ["public", "stanford"]), true);
assert.equal(F.visibleAudience("open_to_public", []), true);

let state = F.filterState(cases.events, cases.days, []);
assert.deepEqual(state.rows, [true, true, true, true]);
assert.equal(state.visible, 4);
assert.equal(state.totalLabel, "4 events.");
assert.equal(state.days["2026-09-27"].hidden, false);
assert.equal(state.days["2026-09-27"].label, "No events");
assert.equal(state.showEmpty, false);
assert.match(state.note, /^Showing all events/);

state = F.filterState(cases.events, cases.days, ["public"]);
assert.deepEqual(state.rows, [true, false, false, true]);
assert.equal(state.visible, 2);
assert.equal(state.totalLabel, "2 of 4 events.");
assert.equal(state.days["2026-09-24"].label, "1 event");
assert.equal(state.days["2026-09-24"].hidden, false);
assert.equal(state.days["2026-09-25"].hidden, true);
assert.equal(state.days["2026-09-25"].jumpHidden, true);
assert.equal(state.days["2026-09-26"].label, "1 event");
assert.equal(state.days["2026-09-27"].hidden, true);
assert.equal(state.note, "Showing 2 of 4 events — Public.");

state = F.filterState(cases.events, cases.days, ["stanford"]);
assert.deepEqual(state.rows, [false, true, false, false]);
assert.equal(state.days["2026-09-24"].label, "1 event");
assert.equal(state.days["2026-09-26"].hidden, true);
assert.equal(state.note, "Showing 1 of 4 events — Stanford only.");

state = F.filterState(cases.events, cases.days, ["public", "stanford"]);
assert.deepEqual(state.rows, [true, true, false, true]);
assert.equal(state.visible, 3);
assert.equal(state.days["2026-09-25"].hidden, true);
assert.equal(state.totalLabel, "3 of 4 events.");
assert.equal(state.note, "Showing 3 of 4 events — Public and Stanford only.");

state = F.filterState(
  [{audience: "stanford_only", day: "2026-09-24"}],
  ["2026-09-24"],
  ["public"]
);
assert.equal(state.visible, 0);
assert.equal(state.showEmpty, true);
assert.equal(state.days["2026-09-24"].hidden, true);
assert.equal(state.totalLabel, "0 of 1 event.");
console.log("ok");
"""
        )
        self.assertIn("ok", _node(source))

    def test_bootstrap_sets_filter_attribute_before_paint(self):
        html = render_html([_ev()], now=NOW)
        bootstrap = _script(html, "audience-filter-bootstrap")
        source = r"""
function run(search, hash) {
  globalThis.document = {
    documentElement: {
      attrs: {},
      setAttribute(name, value) { this.attrs[name] = value; }
    }
  };
  globalThis.location = {search: search, hash: hash};
""" + bootstrap + r"""
  return document.documentElement.attrs["data-audience-filter"];
}
const assert = require("node:assert");
assert.equal(run("", ""), "all");
assert.equal(run("?audience=public", "#d-2026-09-24"), "public");
assert.equal(run("", "#audience=stanford"), "stanford");
assert.equal(run("?audience=open_to_public,stanford_only", ""), "public,stanford");
assert.equal(run("?audience=unknown", ""), "all");
console.log("ok");
"""
        self.assertIn("ok", _node(source))


if __name__ == "__main__":
    unittest.main()
