"""T2-report-download-host: a provider-supplied report URL is host-checked.

`run_search_term_report` used to `httpx.get(status_data["url"])` with no host
check, so whatever URL the Ads API status payload carried became a request -
any host, any scheme (SSRF, and an Amazon-reachable path). These tests prove the
download is refused unless it is https on the Ads API host or an AWS S3 host,
and that the refusal happens BEFORE any request.
"""
from __future__ import annotations

import socket
import unittest
from unittest import mock

from importers.ads_api_importer import (
    AdsAPIImporter,
    UnsafeReportURL,
    assert_allowed_report_url,
    is_allowed_report_url,
)

# Google Cloud Storage, a plausible provider payload. Google's public metadata
# endpoint, loopback and the classic IMDS address are the SSRF shapes.
REFUSED = (
    "https://storage.googleapis.com/amazon-ads/report.csv",
    "https://evil.example.com/report.csv",
    "https://www.amazon.com/dp/B0TEST1234",
    "https://s3.amazonaws.com.evil.example/report.csv",
    "https://evil-amazonaws.com/report.csv",
    "https://s3.amazonaws.com@evil.example/report.csv",
    "http://s3.amazonaws.com/report.csv",
    "https://s3.amazonaws.com:8443/report.csv",
    "https://169.254.169.254/latest/meta-data/",
    "https://127.0.0.1:9000/report.csv",
    "https://[::1]/report.csv",
    "ftp://s3.amazonaws.com/report.csv",
    "file:///etc/passwd",
    "//s3.amazonaws.com/report.csv",
    "",
    None,
)

ALLOWED = (
    "https://advertising-api.amazon.com/v1/reports/r1/download",
    "https://s3.amazonaws.com/bucket/report.csv",
    "https://s3.us-east-1.amazonaws.com/bucket/report.csv",
    "https://amazon-advertising-api-reports-prod-us-east-1.s3.amazonaws.com/report.csv.gz",
    "https://s3.amazonaws.com:443/bucket/report.csv",
)


class ReportURLPolicyTests(unittest.TestCase):
    def test_expected_endpoints_allowed(self):
        for url in ALLOWED:
            with self.subTest(url=url):
                self.assertTrue(is_allowed_report_url(url))
                self.assertEqual(assert_allowed_report_url(url), url)

    def test_other_hosts_and_schemes_refused(self):
        for url in REFUSED:
            with self.subTest(url=url):
                self.assertFalse(is_allowed_report_url(url))
                with self.assertRaises(UnsafeReportURL):
                    assert_allowed_report_url(url)


class _RecordRequest:
    """httpx.get / sockets record an attempt instead of performing one."""

    def __enter__(self):
        def _boom(*a, **k):
            raise AssertionError("network request attempted - the host check ran too late")

        self.get = mock.patch("httpx.get", side_effect=_boom)
        self.socket = mock.patch.object(socket, "socket", side_effect=_boom)
        self.conn = mock.patch.object(socket, "create_connection", side_effect=_boom)
        self.get_mock = self.get.start()
        self.socket.start()
        self.conn.start()
        return self.get_mock

    def __exit__(self, *exc_info):
        self.conn.stop()
        self.socket.stop()
        self.get.stop()
        return False


class ReportDownloadRefusalTests(unittest.TestCase):
    def _importer(self, report_url):
        # Bypass __init__ (it opens the data layer); the download path only
        # needs _enabled, _api_post, _api_get.
        importer = object.__new__(AdsAPIImporter)
        importer._enabled = True
        importer.db = mock.MagicMock()
        importer._api_post = mock.Mock(return_value={"reportId": "r-1"})
        importer._api_get = mock.Mock(
            return_value={"status": "COMPLETED", "url": report_url})
        return importer

    def test_hostile_url_refused_before_any_request(self):
        for url in REFUSED[:6]:
            with self.subTest(url=url):
                importer = self._importer(url)
                with _RecordRequest() as get_mock, mock.patch(
                        "importers.ads_api_importer.time.sleep"):
                    with self.assertRaises(UnsafeReportURL):
                        importer.run_search_term_report()
                get_mock.assert_not_called()

    def test_allowed_s3_url_is_still_downloaded(self):
        importer = self._importer(ALLOWED[2])
        download = mock.MagicMock()
        download.text = ""  # empty payload: returns before touching the DB
        with mock.patch("httpx.get", return_value=download) as get_mock, \
                mock.patch("importers.ads_api_importer.time.sleep"):
            result = importer.run_search_term_report()
        self.assertEqual(get_mock.call_count, 1)
        self.assertEqual(get_mock.call_args[0][0], ALLOWED[2])
        self.assertEqual(result["imported"], 0)


if __name__ == "__main__":
    unittest.main()
