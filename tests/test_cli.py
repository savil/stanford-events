"""Per-source failures stay inside the job."""

from __future__ import annotations

import unittest

from stanford_events.__main__ import _run_source


class CliTests(unittest.TestCase):
    def test_source_error_is_recorded_and_does_not_raise(self):
        errors: list[dict] = []

        def boom():
            raise RuntimeError("calendar down")

        self.assertEqual(_run_source("hai", boom, errors), [])
        self.assertEqual(errors[0]["source"], "hai")
        self.assertIn("RuntimeError: calendar down", errors[0]["error"])
        self.assertIn("Traceback", errors[0]["traceback"])


if __name__ == "__main__":
    unittest.main()
