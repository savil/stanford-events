"""Cross-source near-duplicate collapsing."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from stanford_events.normalize import PT, build_event, dedupe, iter_window_dates, titles_near

PTZ = ZoneInfo("America/Los_Angeles")


def _ev(**kwargs):
    defaults = dict(
        title="Example talk",
        start=datetime(2026, 10, 2, 9, 0, tzinfo=PTZ),
        url="https://example.test/a",
        source_name="Stanford Events (Localist)",
        source_url="https://events.stanford.edu/",
        audience="unknown",
    )
    defaults.update(kwargs)
    return build_event(**defaults)


class TitleTests(unittest.TestCase):
    def test_exact_and_short_suffix(self):
        self.assertTrue(
            titles_near(
                "Bay Area Tech Economics Seminar",
                "Bay Area Tech Economics Seminar with Rehan Khan",
            )
        )
        self.assertTrue(titles_near("Same Title", "same title"))

    def test_unrelated_titles(self):
        self.assertFalse(titles_near("AI seminar", "AI seminar on robots, policy, and money"))
        self.assertFalse(titles_near("Office hours", "Department coffee"))


class DedupeTests(unittest.TestCase):
    def test_exact_cross_source_same_start(self):
        a = _ev(
            title="World Development Report",
            location="Vidalakis Dining Hall",
            audience="unknown",
            source_name="Stanford HAI",
            source_url="https://hai.stanford.edu/events",
            url="https://hai.stanford.edu/events/wdr",
        )
        b = _ev(
            title="World Development Report",
            location=None,
            audience="open_to_public",
            description="A public briefing on the report.",
        )
        out = dedupe([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["audience"], "open_to_public")
        self.assertEqual(out[0]["location"], "Vidalakis Dining Hall")
        self.assertIn("Stanford HAI", out[0]["also_sources"])

    def test_date_only_midnight_merges_with_timed_listing(self):
        hai = _ev(
            title="Empirical Methods in the Age of AI",
            start="2026-10-02T00:00:00-07:00",
            source_name="Stanford HAI",
            source_url="https://hai.stanford.edu/events",
            url="https://hai.stanford.edu/events/empirical",
            audience="unknown",
        )
        localist = _ev(
            title="Empirical Methods in the Age of AI",
            start="2026-10-02T08:00:00-07:00",
            end="2026-10-02T18:00:00-07:00",
            location="Simonyi Conference Center",
            audience="open_to_public",
        )
        out = dedupe([hai, localist])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["start"].startswith("2026-10-02T08:00:00"))
        self.assertEqual(out[0]["audience"], "open_to_public")
        self.assertEqual(out[0]["location"], "Simonyi Conference Center")

    def test_same_title_different_clock_times_stay(self):
        morning = _ev(title="Lab tour", start="2026-10-02T09:00:00-07:00")
        afternoon = _ev(title="Lab tour", start="2026-10-02T15:00:00-07:00", url="https://example.test/b")
        out = dedupe([morning, afternoon])
        self.assertEqual(len(out), 2)

    def test_same_title_different_days_stay(self):
        d1 = _ev(title="Exhibition", start="2026-10-02T10:00:00-07:00")
        d2 = _ev(title="Exhibition", start="2026-10-03T10:00:00-07:00")
        self.assertEqual(len(dedupe([d1, d2])), 2)

    def test_near_title_same_start(self):
        a = _ev(title="Bay Area Tech Economics Seminar", start="2026-10-20T18:30:00-07:00")
        b = _ev(
            title="Bay Area Tech Economics Seminar with Rehan Khan",
            start="2026-10-20T18:30:00-07:00",
            source_name="Stanford HAI",
            source_url="https://hai.stanford.edu/events",
            url="https://hai.stanford.edu/events/bate",
        )
        out = dedupe([a, b])
        self.assertEqual(len(out), 1)
        names = {out[0]["source_name"], *out[0].get("also_sources", [])}
        self.assertEqual(
            names,
            {"Stanford Events (Localist)", "Stanford HAI"},
        )

    def test_window_is_today_through_plus_30(self):
        now = datetime(2026, 9, 24, 15, 0, tzinfo=PT)
        dates = iter_window_dates(days=30, now=now)
        self.assertEqual(len(dates), 31)
        self.assertEqual(dates[0].isoformat(), "2026-09-24")
        self.assertEqual(dates[-1].isoformat(), "2026-10-24")


if __name__ == "__main__":
    unittest.main()
