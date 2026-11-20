"""Offline transport regressions with real pandas/polars frame conversion."""

import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
import traceback

# Import the native frame libraries before the temporary package stand-ins so
# restoring sys.modules does not unload their compiled dependencies.
import pandas
import polars


def load_provider():
    name = "investing_algorithm_framework.infrastructure.data_providers.fxmacrodata"
    modules = {}
    for package in (
        "investing_algorithm_framework",
        "investing_algorithm_framework.domain",
        "investing_algorithm_framework.infrastructure",
        "investing_algorithm_framework.infrastructure.data_providers",
        "investing_algorithm_framework.infrastructure.data_providers.ohlcv_base",
    ):
        modules[package] = types.ModuleType(package)
    modules["investing_algorithm_framework.domain"].OperationalException = type(
        "OperationalException", (Exception,), {}
    )
    modules[
        "investing_algorithm_framework.infrastructure.data_providers.ohlcv_base"
    ].OHLCVDataProviderBase = object
    path = (
        Path(__file__).resolve().parents[3]
        / "investing_algorithm_framework/infrastructure/data_providers/fxmacrodata.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    assert module.pd is pandas
    assert module.pl is polars
    return module


adapter = load_provider()
ROW = {"date": "2026-10-20", "val": 1.25}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.provider = adapter.FXMacroDataOHLCVDataProvider.__new__(
            adapter.FXMacroDataOHLCVDataProvider
        )
        self.provider.base_url = "https://example.invalid/v1"
        self.provider.timeout = 10
        self.provider._get_optional_api_key = Mock(return_value="test-key")
        self.provider._get_provider_interval = Mock(return_value="daily")

    def download(self):
        return self.provider._download_ohlcv(
            "EURUSD",
            "1d",
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 20, tzinfo=timezone.utc),
        )

    def pages(self, payloads):
        responses = [io.BytesIO(json.dumps(payload).encode()) for payload in payloads]
        with patch.object(adapter, "urlopen", side_effect=responses) as fetch:
            result = self.download()
        self.assertTrue(all(response.closed for response in responses))
        return result, fetch

    def test_valid_frame(self):
        frame, _ = self.pages([{"data": [ROW]}])
        self.assertEqual(frame.height, 1)
        self.assertEqual(frame["Close"].to_list(), [1.25])
        self.assertEqual(frame["Volume"].to_list(), [0.0])

    def test_valid_empty_frame(self):
        frame, _ = self.pages([{"data": []}])
        self.assertEqual(frame.height, 0)

    def test_key_is_unredirected(self):
        _, fetch = self.pages([{"data": []}])
        request = fetch.call_args.args[0]
        self.assertEqual(request.unredirected_hdrs["X-api-key"], "test-key")
        self.assertNotIn("X-api-key", request.headers)

    def test_http_error_has_no_private_traceback(self):
        error = HTTPError(
            "https://example.invalid/",
            403,
            "sensitive upstream text",
            {},
            io.BytesIO(b"sensitive upstream text"),
        )
        with patch.object(adapter, "urlopen", side_effect=error):
            try:
                self.download()
            except adapter.OperationalException as caught:
                self.assertNotIn(
                    "sensitive upstream text",
                    "".join(traceback.format_exception(caught)),
                )
            else:
                self.fail("Expected HTTP failure")

    def test_transport_failure_is_not_empty_success(self):
        with patch.object(
            adapter, "urlopen", side_effect=URLError("sensitive upstream text")
        ):
            with self.assertRaises(adapter.OperationalException) as caught:
                self.download()
        self.assertNotIn("sensitive upstream text", str(caught.exception))

    def test_invalid_json_is_not_empty_success(self):
        with patch.object(adapter, "urlopen", return_value=io.BytesIO(b"invalid")):
            with self.assertRaises(adapter.OperationalException) as caught:
                self.download()
        self.assertTrue(caught.exception.__suppress_context__)

    def test_error_payload_is_not_empty_success(self):
        with self.assertRaises(adapter.OperationalException):
            self.pages([{"data": [], "error": "failed"}])

    def test_invalid_rows_are_not_silently_dropped(self):
        with self.assertRaises(adapter.OperationalException):
            self.pages([{"data": [ROW, "invalid"]}])

    def test_repeated_offset_rejected(self):
        with patch.object(adapter, "FXMACRODATA_MAX_PAGES", 2):
            with self.assertRaises(adapter.OperationalException):
                self.pages(
                    [
                        {
                            "data": [ROW],
                            "pagination": {"has_more": True, "next_offset": 0},
                        }
                    ]
                    * 2
                )

    def test_string_offset_rejected(self):
        with patch.object(adapter, "FXMACRODATA_MAX_PAGES", 1):
            with self.assertRaises(adapter.OperationalException):
                self.pages(
                    [
                        {
                            "data": [ROW],
                            "pagination": {"has_more": True, "next_offset": "1"},
                        }
                    ]
                )

    def test_boolean_offset_rejected(self):
        with patch.object(adapter, "FXMACRODATA_MAX_PAGES", 1):
            with self.assertRaises(adapter.OperationalException):
                self.pages(
                    [
                        {
                            "data": [ROW],
                            "pagination": {"has_more": True, "next_offset": True},
                        }
                    ]
                )

    def test_empty_page_claiming_more_rejected(self):
        with self.assertRaises(adapter.OperationalException):
            self.pages(
                [{"data": [], "pagination": {"has_more": True, "next_offset": 1}}]
            )

    def test_page_cap_does_not_return_partial_history(self):
        with patch.object(adapter, "FXMACRODATA_MAX_PAGES", 1):
            with self.assertRaises(adapter.OperationalException):
                self.pages(
                    [
                        {
                            "data": [ROW],
                            "pagination": {"has_more": True, "next_offset": 1},
                        }
                    ]
                )

    def test_two_pages(self):
        frame, fetch = self.pages(
            [
                {"data": [ROW], "pagination": {"has_more": True, "next_offset": 1}},
                {"data": [{"date": "2026-10-19", "val": 1.2}]},
            ]
        )
        self.assertEqual(frame.height, 2)
        self.assertIn("offset=1", fetch.call_args_list[1].args[0].full_url)

    def test_string_has_more_rejected(self):
        with patch.object(adapter, "FXMACRODATA_MAX_PAGES", 1):
            with self.assertRaises(adapter.OperationalException):
                self.pages([{"data": [ROW], "pagination": {"has_more": "false"}}])

    def test_non_dictionary_pagination_rejected(self):
        with self.assertRaises(adapter.OperationalException):
            self.pages([{"data": [ROW], "pagination": "invalid"}])


if __name__ == "__main__":
    unittest.main()
