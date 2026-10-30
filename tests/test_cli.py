"""Per-source failures stay inside the job."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from stanford_events import hai, hci_seminar, html_listings, localist
from stanford_events.__main__ import _run_source, main
from stanford_events.normalize import PT, build_event
from stanford_events.registry import Source, iter_sources

# source_name strings the parsers write today. Fallback matches these.
EXPECTED_SOURCE_NAMES = {
    "localist": ("Stanford Events (Localist)", "Bing Concert Hall (Localist)"),
    "hci_seminar": ("Stanford HCI Seminar",),
    "hai": ("Stanford HAI",),
    "stanford_live": ("Stanford Live",),
    "siepr": ("SIEPR",),
    "kipac": ("KIPAC",),
    "qfarm": ("Q-FARM",),
    "aimi": ("AIMI",),
    "bioengineering": ("Bioengineering",),
    "statistics": ("Statistics",),
    "psychology": ("Psychology",),
    "physics": ("Physics",),
    "art": ("Art & Art History",),
    "law": ("Stanford Law",),
    "fsi": ("FSI",),
    "gse": ("Stanford GSE",),
    "hoover": ("Hoover Institution",),
    "ccrma": ("CCRMA",),
    "neuroscience": ("Wu Tsai Neurosciences",),
    "humanities_center": ("Stanford Humanities Center",),
    "gsb": ("Stanford GSB",),
    "health_library": ("Stanford Health Library",),
    "slac": ("SLAC",),
}


def _event(title: str, source_name: str, start: datetime, url: str = "https://example.test/e"):
    return build_event(
        title=title,
        start=start,
        url=url,
        source_name=source_name,
        source_url="https://example.test/",
        audience="unknown",
    )


def _noon_today() -> datetime:
    return datetime.now(tz=PT).replace(hour=12, minute=0, second=0, microsecond=0)


class CliTests(unittest.TestCase):
    def test_source_error_is_recorded_and_does_not_raise(self):
        errors: list[dict] = []

        def boom(days: int):
            del days
            raise RuntimeError("calendar down")

        source = Source("hai", "HAI", boom)
        self.assertEqual(_run_source(source, 30, [], errors), [])
        self.assertEqual(errors[0]["source"], "hai")
        self.assertIn("RuntimeError: calendar down", errors[0]["error"])
        self.assertIn("Traceback", errors[0]["traceback"])
        self.assertNotIn("fallback_events", errors[0])

    def test_source_names_match_what_parsers_write(self):
        by_key = {source.key: source.source_names for source in iter_sources()}
        self.assertEqual(by_key, EXPECTED_SOURCE_NAMES)
        flat = [name for names in by_key.values() for name in names]
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(localist.SOURCE_NAME, EXPECTED_SOURCE_NAMES["localist"][0])
        self.assertEqual(localist.BING_SOURCE_NAME, EXPECTED_SOURCE_NAMES["localist"][1])
        self.assertEqual(hci_seminar.SOURCE_NAME, EXPECTED_SOURCE_NAMES["hci_seminar"][0])
        self.assertEqual(hai.SOURCE_NAME, EXPECTED_SOURCE_NAMES["hai"][0])
        self.assertEqual(
            html_listings.NEUROSCIENCE_SOURCE_NAME,
            EXPECTED_SOURCE_NAMES["neuroscience"][0],
        )
        self.assertEqual(
            html_listings.HUMANITIES_SOURCE_NAME,
            EXPECTED_SOURCE_NAMES["humanities_center"][0],
        )
        self.assertEqual(html_listings.GSB_SOURCE_NAME, EXPECTED_SOURCE_NAMES["gsb"][0])
        self.assertEqual(
            html_listings.HEALTH_LIBRARY_SOURCE_NAME,
            EXPECTED_SOURCE_NAMES["health_library"][0],
        )
        self.assertEqual(html_listings.SLAC_SOURCE_NAME, EXPECTED_SOURCE_NAMES["slac"][0])

    def test_failed_source_keeps_only_its_in_window_events(self):
        today = _noon_today()
        stale = today - timedelta(days=3)

        def fresh(days: int):
            del days
            return [
                _event(
                    "Fresh talk",
                    "Stanford HAI",
                    today + timedelta(days=1),
                    url="https://hai.example/fresh",
                )
            ]

        def down(days: int):
            del days
            raise TimeoutError("read timed out")

        sources = [
            Source(
                "localist",
                "Localist",
                down,
                source_names=("Stanford Events (Localist)", "Bing Concert Hall (Localist)"),
            ),
            Source("hai", "HAI", fresh, source_names=("Stanford HAI",)),
        ]
        previous = [
            _event(
                "Kept seminar",
                "Stanford Events (Localist)",
                today,
                url="https://events.example/kept",
            ),
            _event(
                "Old seminar",
                "Stanford Events (Localist)",
                stale,
                url="https://events.example/old",
            ),
            _event(
                "Bing night",
                "Bing Concert Hall (Localist)",
                today,
                url="https://events.example/bing",
            ),
            _event("Stale HAI", "Stanford HAI", today, url="https://hai.example/stale"),
            {"source_name": "Stanford Events (Localist)", "title": "missing id"},
            "not-an-event",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "events.json").write_text(json.dumps(previous), encoding="utf-8")
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 0)
            errors = json.loads((out / "errors.json").read_text(encoding="utf-8"))
            self.assertEqual([err["source"] for err in errors], ["localist"])
            self.assertIn("TimeoutError: read timed out", errors[0]["error"])
            self.assertIn("Traceback", errors[0]["traceback"])
            self.assertEqual(errors[0]["fallback_events"], 2)
            titles = {ev["title"] for ev in json.loads((out / "events.json").read_text())}
            self.assertEqual(titles, {"Kept seminar", "Bing night", "Fresh talk"})
            html = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("Kept 2 events from the last listing.", html)
            self.assertIn("Failed sources keep events from the last listing", html)

    def test_every_source_failing_republishes_carried_events(self):
        today = _noon_today()

        def down(days: int):
            del days
            raise RuntimeError("down")

        sources = [
            Source("localist", "Localist", down, source_names=("Stanford Events (Localist)",)),
            Source("hci_seminar", "HCI Seminar", down, source_names=("Stanford HCI Seminar",)),
        ]
        previous = [
            _event("Still listed", "Stanford Events (Localist)", today),
            _event("Friday talk", "Stanford HCI Seminar", today, url="https://hci.example/t"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "events.json").write_text(json.dumps(previous) + "\n", encoding="utf-8")
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 0)
            errors = json.loads((out / "errors.json").read_text(encoding="utf-8"))
            self.assertEqual({err["source"] for err in errors}, {"localist", "hci_seminar"})
            self.assertTrue(errors)  # non-empty still means the run saw failures
            self.assertTrue(all(err["fallback_events"] == 1 for err in errors))
            titles = {ev["title"] for ev in json.loads((out / "events.json").read_text())}
            self.assertEqual(titles, {"Still listed", "Friday talk"})

    def test_stale_previous_rows_do_not_replace_an_empty_failure(self):
        stale = _noon_today() - timedelta(days=5)

        def down(days: int):
            del days
            raise RuntimeError("down")

        sources = [Source("a", "A", down, source_names=("A",))]
        previous_text = json.dumps([_event("Gone", "A", stale)]) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / "events.json"
            path.write_text(previous_text, encoding="utf-8")
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 1)
            self.assertEqual(path.read_text(encoding="utf-8"), previous_text)
            errors = json.loads((out / "errors.json").read_text(encoding="utf-8"))
            self.assertEqual(errors[0]["source"], "a")
            self.assertNotIn("fallback_events", errors[0])

    def test_unreadable_previous_listing_is_skipped(self):
        today = _noon_today()

        def fresh(days: int):
            del days
            return [_event("Fresh", "Stanford HAI", today, url="https://hai.example/fresh")]

        def down(days: int):
            del days
            raise RuntimeError("calendar down")

        sources = [
            Source("hai", "HAI", fresh, source_names=("Stanford HAI",)),
            Source("broken", "Broken", down, source_names=("Broken",)),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "events.json").write_text("{", encoding="utf-8")
            with patch("stanford_events.__main__.iter_sources", return_value=sources):
                code = main(["--out", str(out), "--days", "30"])
            self.assertEqual(code, 0)
            errors = json.loads((out / "errors.json").read_text(encoding="utf-8"))
            self.assertEqual([err["source"] for err in errors], ["broken"])
            self.assertNotIn("fallback_events", errors[0])
            titles = [ev["title"] for ev in json.loads((out / "events.json").read_text())]
            self.assertEqual(titles, ["Fresh"])


if __name__ == "__main__":
    unittest.main()
