"""Public by-day HTML page."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
