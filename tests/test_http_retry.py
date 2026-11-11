"""Retries for transient timeouts and dropped connections."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from stanford_events import http_util
from stanford_events.http_util import MAX_ATTEMPTS, get


def _response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


class HttpRetryTests(unittest.TestCase):
    def setUp(self):
        http_util._last_request_at = 0.0

    def tearDown(self):
        http_util._last_request_at = 0.0

    def test_success_does_not_retry(self):
        resp = _response()
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch("stanford_events.http_util.requests.get", return_value=resp) as get_mock,
        ):
            self.assertIs(get("https://events.stanford.edu/api/2/events"), resp)
        self.assertEqual(get_mock.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("StanfordEvents/1.0", get_mock.call_args.kwargs["headers"]["User-Agent"])
        self.assertEqual(get_mock.call_args.kwargs["timeout"], 30)

    def test_read_timeout_then_success(self):
        resp = _response()
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch(
                "stanford_events.http_util.requests.get",
                side_effect=[requests.exceptions.ReadTimeout("read timed out"), resp],
            ) as get_mock,
        ):
            out = get(
                "https://events.stanford.edu/api/2/events",
                params={"page": 1},
                timeout=30,
            )
        self.assertIs(out, resp)
        self.assertEqual(get_mock.call_count, 2)
        sleep.assert_called_once_with(1.0)
        self.assertEqual(get_mock.call_args.kwargs["params"], {"page": 1})
        self.assertEqual(get_mock.call_args.kwargs["timeout"], 30)

    def test_connect_timeout_exhausts_attempts(self):
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch(
                "stanford_events.http_util.requests.get",
                side_effect=requests.exceptions.ConnectTimeout("timed out"),
            ) as get_mock,
        ):
            with self.assertRaises(requests.exceptions.ConnectTimeout):
                get("https://hci.stanford.edu/seminar/")
        self.assertEqual(get_mock.call_count, MAX_ATTEMPTS)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

    def test_connection_reset_is_retried(self):
        resp = _response()
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch(
                "stanford_events.http_util.requests.get",
                side_effect=[requests.exceptions.ConnectionError("connection reset"), resp],
            ) as get_mock,
        ):
            self.assertIs(get("https://hci.stanford.edu/seminar/"), resp)
        self.assertEqual(get_mock.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_tls_handshake_drop_is_retried(self):
        resp = _response()
        exc = requests.exceptions.SSLError(
            "SSLEOFError: UNEXPECTED_EOF_WHILE_READING EOF occurred in violation of protocol"
        )
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep"),
            patch(
                "stanford_events.http_util.requests.get",
                side_effect=[exc, resp],
            ) as get_mock,
        ):
            self.assertIs(get("https://hci.stanford.edu/seminar/"), resp)
        self.assertEqual(get_mock.call_count, 2)

    def test_certificate_verification_failure_is_not_retried(self):
        exc = requests.exceptions.SSLError(
            "certificate verify failed: unable to get local issuer certificate"
        )
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch("stanford_events.http_util.requests.get", side_effect=exc) as get_mock,
        ):
            with self.assertRaises(requests.exceptions.SSLError):
                get("https://hci.stanford.edu/seminar/")
        self.assertEqual(get_mock.call_count, 1)
        sleep.assert_not_called()

    def test_nested_certificate_error_is_not_retried(self):
        exc = requests.exceptions.SSLError("Max retries exceeded")
        exc.__cause__ = type("SSLCertVerificationError", (Exception,), {})(
            "certificate verify failed"
        )
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch("stanford_events.http_util.requests.get", side_effect=exc) as get_mock,
        ):
            with self.assertRaises(requests.exceptions.SSLError):
                get("https://med.stanford.edu/healthlibrary/lectures-events.html")
        self.assertEqual(get_mock.call_count, 1)
        sleep.assert_not_called()

    def test_http_status_is_not_retried(self):
        resp = _response()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        with (
            patch("stanford_events.http_util.MIN_INTERVAL_SEC", 0),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch("stanford_events.http_util.requests.get", return_value=resp) as get_mock,
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                get("https://example.test/events")
        self.assertEqual(get_mock.call_count, 1)
        sleep.assert_not_called()

    def test_rate_limit_still_waits(self):
        http_util._last_request_at = 1000.0
        resp = _response()
        with (
            patch("stanford_events.http_util.time.monotonic", return_value=1000.1),
            patch("stanford_events.http_util.time.sleep") as sleep,
            patch("stanford_events.http_util.requests.get", return_value=resp),
        ):
            get("https://example.test/")
        self.assertEqual(sleep.call_count, 1)
        self.assertAlmostEqual(sleep.call_args.args[0], 0.3)


if __name__ == "__main__":
    unittest.main()
