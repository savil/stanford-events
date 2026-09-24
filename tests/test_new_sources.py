"""Parsers for calendars added beyond Localist, HCI, and HAI."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from stanford_events.ccrma import event_from_detail, event_urls_from_month
from stanford_events.fsi import events_from_fsi_payload
from stanford_events.gse import events_from_gse_payload
from stanford_events.hoover import events_from_hoover_payload
from stanford_events.hs_events import events_from_hs_payload
from stanford_events.html_listings import (
    parse_gsb,
    parse_health_library,
    parse_humanities_center,
    parse_neuroscience,
    parse_slac,
)
from stanford_events.law_events import events_from_tribe_payload
from stanford_events.normalize import PT, classify_audience_from_text, classify_audience_names
from stanford_events.registry import Source
from stanford_events.stanford_live import events_from_live_payload
from stanford_events.sws import events_from_sws_payload
from stanford_events.__main__ import main


SWS_FIXTURE = {
    "data": [
        {
            "id": "localist-mirror",
            "attributes": {
                "status": True,
                "title": "Already on Localist",
                "su_event_date_time": {
                    "value": "2026-10-01T22:00:00+00:00",
                    "end_value": "2026-10-01T23:00:00+00:00",
                },
                "su_event_source": {"uri": "https://events.stanford.edu/event/already"},
                "path": {"alias": "/events/already"},
            },
            "relationships": {"su_event_audience": {"data": []}},
        },
        {
            "id": "native",
            "attributes": {
                "status": True,
                "title": "KIPAC Tea Talk: Dark matter lenses",
                "su_event_date_time": {
                    "value": "2026-10-02T18:00:00+00:00",
                    "end_value": "2026-10-02T19:00:00+00:00",
                },
                "su_event_dek": "Campus, PAB 102/103",
                "su_event_source": None,
                "path": {"alias": "/events/kipac-tea-talk/dark-matter"},
                "body": None,
            },
            "relationships": {
                "su_event_audience": {
                    "data": [{"type": "taxonomy_term--event_audience", "id": "aud-1"}]
                }
            },
        },
    ],
    "included": [
        {
            "id": "aud-1",
            "attributes": {"name": "Faculty/Staff"},
        }
    ],
}

HS_FIXTURE = {
    "data": [
        {
            "attributes": {
                "status": True,
                "title": "Colloquium",
                "field_hs_event_date": {
                    "value": "2026-09-30T22:45:00+00:00",
                    "end_value": "2026-09-30T23:45:00+00:00",
                },
                "field_hs_event_location": "Building 420\nRoom 050",
                "field_hs_event_link": None,
                "path": {"alias": "/events/colloquium-83"},
                "body": {"value": "<p>Department colloquium.</p>"},
            },
            "relationships": {
                "field_hs_event_audience": {"data": []},
                "field_hs_event_speaker": {
                    "data": [{"type": "hs_entity--event_collections__speaker", "id": "spk"}]
                },
            },
        },
        {
            "attributes": {
                "status": True,
                "title": "Physics colloquium on Localist",
                "field_hs_event_date": {"value": "2026-10-06T22:30:00+00:00"},
                "field_hs_event_link": {
                    "uri": "https://events.stanford.edu/event/physics-colloquium"
                },
                "path": {"alias": "/events/physics-localist"},
            },
            "relationships": {},
        },
    ],
    "included": [{"id": "spk", "attributes": {"label": "Ada Lovelace"}}],
}


class AudienceTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(classify_audience_names(["Everyone", "Students"]), "open_to_public")
        self.assertEqual(classify_audience_names(["Faculty/Staff", " Alumni/Friends "]), "stanford_only")
        self.assertEqual(classify_audience_names(["By Invitation Only"]), "unknown")
        self.assertEqual(classify_audience_names([]), "unknown")

    def test_free_and_open_phrasing(self):
        self.assertEqual(
            classify_audience_from_text("Webinars are free and open to adults with diabetes."),
            "open_to_public",
        )
        self.assertEqual(
            classify_audience_from_text("This session is free and open to Stanford affiliates."),
            "stanford_only",
        )
        self.assertEqual(
            classify_audience_from_text("Registration details will be posted later."),
            "unknown",
        )
        self.assertEqual(
            classify_audience_from_text("Open to the Public"),
            "open_to_public",
        )


class SwsTests(unittest.TestCase):
    def test_skips_localist_mirrors_and_maps_audience(self):
        events = events_from_sws_payload(
            SWS_FIXTURE,
            source_name="KIPAC",
            source_url="https://kipac.stanford.edu/events/upcoming-events",
            origin="https://kipac.stanford.edu",
        )
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["title"], "KIPAC Tea Talk: Dark matter lenses")
        self.assertEqual(ev["audience"], "stanford_only")
        self.assertEqual(ev["location"], "Campus, PAB 102/103")
        self.assertTrue(ev["url"].endswith("/events/kipac-tea-talk/dark-matter"))


class HsTests(unittest.TestCase):
    def test_speaker_and_localist_skip(self):
        events = events_from_hs_payload(
            HS_FIXTURE,
            source_name="Psychology",
            source_url="https://psychology.stanford.edu/news-events/upcoming-events",
            origin="https://psychology.stanford.edu",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Ada Lovelace — Colloquium")
        self.assertEqual(events[0]["audience"], "unknown")
        self.assertIn("Building 420", events[0]["location"])


class FeedTests(unittest.TestCase):
    def test_law_tribe(self):
        events = events_from_tribe_payload(
            {
                "events": [
                    {
                        "status": "publish",
                        "title": "Anatomy of a Mass Tort",
                        "start_date": "2026-09-24 12:45:00",
                        "end_date": "2026-09-24 13:45:00",
                        "timezone": "America/Los_Angeles",
                        "url": "https://law.stanford.edu/event/mass-tort/",
                        "description": "<p>The seminar is open to the public.</p>",
                        "venue": {"venue": "@ SLS: Room 290", "address": "559 Nathan Abbott Way", "city": "Stanford"},
                    },
                    {"status": "publish", "title": "Hidden", "hide_from_listings": True, "start_date": "2026-09-24 10:00:00"},
                ]
            }
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["audience"], "open_to_public")
        self.assertIn("Room 290", events[0]["location"])
        self.assertTrue(events[0]["start"].startswith("2026-09-24T12:45:00"))

    def test_fsi(self):
        events = events_from_fsi_payload(
            {
                "data": [
                    {
                        "attributes": {
                            "status": True,
                            "title": "Unpacking the meeting",
                            "field_event_periods": {
                                "value": "2026-09-28T16:00:00-07:00",
                                "end_value": "2026-09-28T17:30:00-07:00",
                            },
                            "field_location": {"processed": "<p>Encina Hall</p>"},
                            "field_card_select_description": "A discussion.",
                            "path": {"alias": "/events/unpacking"},
                        }
                    }
                ]
            }
        )
        self.assertEqual(events[0]["location"], "Encina Hall")
        self.assertEqual(events[0]["audience"], "unknown")
        self.assertTrue(events[0]["url"].endswith("/events/unpacking"))

    def test_gse_admission(self):
        events = events_from_gse_payload(
            {
                "data": [
                    {
                        "attributes": {
                            "status": True,
                            "title": "STEP Info Session",
                            "field_hide_from_public": False,
                            "field_event_admission": ["open_to_public"],
                            "field_location_name": "Zoom",
                            "field_summary": None,
                            "path": {"alias": "/events/step-info-session"},
                            "field_start_end_datetimes": [
                                {"value": "2026-09-25T10:00:00-07:00", "end_value": "2026-09-25T11:00:00-07:00"}
                            ],
                        }
                    },
                    {
                        "attributes": {
                            "status": True,
                            "title": "Internal picnic",
                            "field_hide_from_public": False,
                            "field_event_admission": ["gse_community_only"],
                            "field_location_name": "Cubberley",
                            "path": {"alias": "/events/picnic"},
                            "field_start_end_datetimes": [
                                {"value": "2026-09-24T12:00:00-07:00", "end_value": "2026-09-24T14:00:00-07:00"}
                            ],
                        }
                    },
                    {
                        "attributes": {
                            "status": True,
                            "title": "Hidden",
                            "field_hide_from_public": True,
                            "field_event_admission": ["open_to_public"],
                            "path": {"alias": "/events/hidden"},
                            "field_start_end_datetimes": [{"value": "2026-09-24T12:00:00-07:00"}],
                        }
                    },
                ]
            }
        )
        by_title = {ev["title"]: ev for ev in events}
        self.assertEqual(set(by_title), {"STEP Info Session", "Internal picnic"})
        self.assertEqual(by_title["STEP Info Session"]["audience"], "open_to_public")
        self.assertEqual(by_title["Internal picnic"]["audience"], "stanford_only")

    def test_hoover(self):
        events = events_from_hoover_payload(
            {
                "data": [
                    {
                        "attributes": {
                            "status": True,
                            "title": "Reclaiming Liberal Education",
                            "field_date": "2026-10-12T16:00:00-07:00",
                            "field_end_date": "2026-10-12T17:15:00-07:00",
                            "field_location": "Zoom",
                            "field_teaser_blurb": None,
                            "path": {"alias": "/events/reclaiming"},
                        }
                    }
                ]
            }
        )
        self.assertEqual(events[0]["audience"], "unknown")
        self.assertEqual(events[0]["location"], "Zoom")
        self.assertTrue(events[0]["url"].startswith("https://www.hoover.org/events/"))

    def test_stanford_live(self):
        events = events_from_live_payload(
            [
                {
                    "ShowInCalendar": True,
                    "Title": "Hysterical",
                    "DisplayTitle": "<em>Hysterical</em>: W. Kamau Bell",
                    "Venue": "Memorial Auditorium",
                    "EventLink": "/events/26-27season/hysterical/",
                    "Summary": None,
                    "Performances": [
                        {"StartDate": "2026-10-01 19:30:00", "EndDate": None},
                        {"StartDate": None},
                    ],
                },
                {"ShowInCalendar": False, "Title": "Hidden", "Performances": [{"StartDate": "2026-10-02 19:00:00"}]},
            ]
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Hysterical: W. Kamau Bell")
        self.assertEqual(events[0]["audience"], "unknown")
        self.assertIn("19:30:00", events[0]["start"])
        self.assertTrue(events[0]["url"].endswith("/hysterical/"))


NEURO_HTML = """
<article class="node node--type-event">
  <h4><a href="/events/wu-tsai-neuro-fall-picnic-2026">Wu Tsai Neuro Fall Picnic 2026</a></h4>
  <time datetime="2026-09-24T16:00:00-07:00">Thursday, September 24, 2026</time>
  <time>4:00pm to 6:00pm PDT</time>
  <div class="location">ChEM-H Courtyard</div>
</article>
"""

SHC_HTML = """
<div class="views-row">
  <div class="views-field views-field-title"><a href="/cesta/events/nostalgia">Nostalgia and the Private Self</a></div>
  <time class="datetime" datetime="2026-09-24T12:15:00-07:00">Thursday, Sep 24, 2026 12:15</time>
  -
  <time class="datetime" datetime="2026-09-24T13:15:00-07:00">1:15pm PDT</time>
  <div class="views-field views-field-field-event-location"><div class="field-content">Wallenberg Hall</div></div>
</div>
"""

GSB_HTML = """
<div class="view__content-row">
  <div class="split-date-time">
    <div class="date">Wednesday, Oct 7, 2026</div>
    <div class="time">4:00pm – 6:30pm</div>
  </div>
  <div class="title"><a href="/events/bridging-ai">Bridging AI &amp; Sustainability</a></div>
  <div class="location-type">Off Campus</div>
  <div class="summary">Open to the public. Please join the panel.</div>
</div>
"""

MED_HTML = """
<h2>LECTURES + EVENTS 2026</h2>
<h2>Yoga and Meditation</h2>
<p>Webinars are free and open to adults with diabetes and their families.</p>
<p>Sunday, September 27<br>8:00 am Pacific Time</p>
<p>Virtual<br>Zoom</p>
<h2>Let's Stay in Touch</h2>
<p>Monday, January 4<br>1:00 pm Pacific Time</p>
"""

SLAC_HTML = """
<div class="c-card">
  <p class="c-card__title"><a class="c-card__link" href="/events/future-lecture">Public Lecture: The Higgs</a></p>
  <div class="c-field__content"><p>Thursday, October 8, 2026</p></div>
</div>
<div class="c-card">
  <p class="c-card__title"><a class="c-card__link" href="/events/old">STEM Community Day 2026</a></p>
  <p>Saturday, September 12</p>
</div>
"""

CCRMA_MONTH = """
<table>
  <td id="calendar_not_date_browser-2026-10-02" class="has-events">
    <a href="/events/seth-cluett">Seth Cluett</a>
    <a href="/calendar/2026-10">month</a>
  </td>
  <td id="calendar_not_date_browser-2026-08-01">
    <a href="/events/old">Old</a>
  </td>
</table>
"""

CCRMA_DETAIL = """
<html><h1>Seth Cluett | a static slice through time</h1>
<div class="node">
  <div class="field field-field-event-date">Date: Wed, 10/02/2026 - 7:30pm - 9:00pm</div>
  <div class="field field-field-location">Location: CCRMA Stage</div>
  <div class="field field-field-intended-audience">Intended Audience: Open to the Public</div>
  <p>Join us for an evening with composer and performer Seth Cluett at CCRMA.</p>
</div></html>
"""


class HtmlTests(unittest.TestCase):
    def test_neuroscience_time_range(self):
        events = parse_neuroscience(NEURO_HTML, "https://neuroscience.stanford.edu/events")
        self.assertEqual(len(events), 1)
        self.assertIn("T16:00:00", events[0]["start"])
        self.assertIn("T18:00:00", events[0]["end"])
        self.assertEqual(events[0]["location"], "ChEM-H Courtyard")

    def test_humanities_center(self):
        events = parse_humanities_center(SHC_HTML, "https://shc.stanford.edu/stanford-humanities-center/events")
        self.assertEqual(events[0]["location"], "Wallenberg Hall")
        self.assertIn("T12:15:00", events[0]["start"])

    def test_gsb_public_summary(self):
        events = parse_gsb(GSB_HTML, "https://www.gsb.stanford.edu/events")
        self.assertEqual(events[0]["audience"], "open_to_public")
        self.assertIn("T16:00:00", events[0]["start"])
        self.assertEqual(events[0]["location"], "Off Campus")

    def test_health_library_stops_at_footer(self):
        events = parse_health_library(MED_HTML)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Yoga and Meditation")
        self.assertEqual(events[0]["audience"], "open_to_public")
        self.assertIn("Virtual", events[0]["location"])

    def test_slac_dated_cards(self):
        events = parse_slac(SLAC_HTML, "https://www6.slac.stanford.edu/news-and-events/events/public-lectures")
        titles = {ev["title"] for ev in events}
        self.assertIn("Public Lecture: The Higgs", titles)
        self.assertIn("STEM Community Day 2026", titles)

    def test_ccrma_month_and_detail(self):
        urls = event_urls_from_month(
            CCRMA_MONTH,
            "https://ccrma.stanford.edu/calendar/2026-10",
            start=datetime(2026, 9, 24).date(),
            end=datetime(2026, 10, 24).date(),
        )
        self.assertEqual(urls, ["https://ccrma.stanford.edu/events/seth-cluett"])
        ev = event_from_detail(CCRMA_DETAIL, urls[0])
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev["audience"], "open_to_public")
        self.assertEqual(ev["location"], "CCRMA Stage")
        self.assertIn("T19:30:00", ev["start"])


class CliIsolationTests(unittest.TestCase):
    def test_one_failed_source_does_not_fail_the_run(self):
        start = datetime.now(tz=PT).replace(hour=15, minute=0, second=0, microsecond=0)

        def ok(days: int):
            del days
            from stanford_events.normalize import build_event

            return [
                build_event(
                    title="Still here",
                    start=start,
                    url="https://example.test/event",
                    source_name="Example",
                    source_url="https://example.test/",
                    audience="unknown",
                )
            ]

        def bad(days: int):
            del days
            raise RuntimeError("calendar down")

        sources = [
            Source("example", "Example", ok),
            Source("broken", "Broken", bad),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 0)
            errors = json.loads((out / "errors.json").read_text())
            self.assertEqual([err["source"] for err in errors], ["broken"])
            events = json.loads((out / "events.json").read_text())
            self.assertEqual([ev["title"] for ev in events], ["Still here"])

    def test_every_source_failing_keeps_previous_listing(self):
        def bad(days: int):
            del days
            raise RuntimeError("down")

        sources = [Source("a", "A", bad), Source("b", "B", bad)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            previous = out / "events.json"
            previous.write_text("[]\n", encoding="utf-8")
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 1)
            self.assertEqual(previous.read_text(encoding="utf-8"), "[]\n")
            errors = json.loads((out / "errors.json").read_text())
            self.assertEqual({err["source"] for err in errors}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
