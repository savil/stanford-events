"""TLS trust for the two CERTInext hosts."""

from __future__ import annotations

import base64
import hashlib
import ssl
import unittest
from pathlib import Path

import certifi

from stanford_events.http_util import _EMSIGN_ROOT_PEM, emsign_ca_bundle, verify_for

# Mozilla emSign Root CA - G1 (SHA256 of the DER certificate).
_EMSIGN_ROOT_SHA256 = (
    "40f6af0346a99aa1cd1d555a4e9cce62c7f9634603ee406615833dc8c8d00367"
)


def _pem_der_digests(text: str) -> list[str]:
    digests = []
    body: list[str] = []
    capturing = False
    for line in text.splitlines():
        if "BEGIN CERTIFICATE" in line:
            capturing = True
            body = []
            continue
        if "END CERTIFICATE" in line and capturing:
            der = base64.b64decode("".join(body))
            digests.append(hashlib.sha256(der).hexdigest())
            capturing = False
            continue
        if capturing:
            body.append(line.strip())
    return digests


class HttpUtilTlsTests(unittest.TestCase):
    def test_bundled_root_is_emsign_root_ca_g1(self):
        digests = _pem_der_digests(_EMSIGN_ROOT_PEM.read_text())
        self.assertEqual(digests, [_EMSIGN_ROOT_SHA256])

    def test_only_certinext_hosts_use_the_extra_root(self):
        bundle = verify_for("https://hci.stanford.edu/seminar/")
        self.assertIsInstance(bundle, str)
        self.assertEqual(
            verify_for("https://med.stanford.edu/healthlibrary/lectures-events.html"),
            bundle,
        )
        self.assertEqual(verify_for("https://HCI.STANFORD.EDU/seminar/"), bundle)
        self.assertIs(verify_for("https://events.stanford.edu/api/2/events"), True)
        self.assertIs(verify_for("https://hai.stanford.edu/events"), True)
        self.assertIs(verify_for("https://www.med.stanford.edu/"), True)

        path = Path(bundle)
        self.assertEqual(path, Path(emsign_ca_bundle()))
        digests = _pem_der_digests(path.read_text())
        certifi_digests = _pem_der_digests(Path(certifi.where()).read_text())
        self.assertEqual(digests, [*certifi_digests, _EMSIGN_ROOT_SHA256])
        ctx = ssl.create_default_context(cafile=bundle)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)


if __name__ == "__main__":
    unittest.main()
