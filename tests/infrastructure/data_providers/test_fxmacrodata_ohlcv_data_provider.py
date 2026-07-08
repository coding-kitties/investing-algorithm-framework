import json
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import DataSource
from investing_algorithm_framework.infrastructure import (
    FXMacroDataOHLCVDataProvider,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload.encode("utf-8")


class TestFXMacroDataHasData(TestCase):
    def test_returns_false_for_non_fxmacrodata_market(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eurusd_daily",
            market="YAHOO",
            symbol="EURUSD",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_non_ohlcv_type(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eurusd_ticker",
            market="FXMACRODATA",
            symbol="EURUSD",
            data_type="TICKER",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_true_for_valid_pair(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eurusd_daily",
            market="FXMACRODATA",
            symbol="EUR/USD",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    def test_returns_false_for_invalid_pair(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eur_daily",
            market="FXMACRODATA",
            symbol="EUR",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_unsupported_timeframe(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eurusd_hourly",
            market="FXMACRODATA",
            symbol="EURUSD",
            data_type="OHLCV",
            time_frame="1h",
        )
        self.assertFalse(provider.has_data(data_source))


class TestFXMacroDataGetData(TestCase):
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.fxmacrodata.urlopen"
    )
    def test_get_data_returns_close_only_polars_dataframe(self, mock_urlopen):
        payload = {
            "data": [
                {"date": "2024-01-03", "val": 1.092},
                {"date": "2024-01-01", "val": "1.1038"},
            ]
        }
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["accept"] = request.headers["Accept"]
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(payload))

        mock_urlopen.side_effect = fake_urlopen

        provider = FXMacroDataOHLCVDataProvider(
            symbol="EURUSD",
            market="FXMACRODATA",
            time_frame="1d",
            timeout=12,
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(
            data.columns,
            ["Datetime", "Open", "High", "Low", "Close", "Volume"],
        )
        self.assertEqual(data["Close"].to_list(), [1.1038, 1.092])
        self.assertEqual(data["Open"].to_list(), [1.1038, 1.092])
        self.assertEqual(data["Volume"].to_list(), [0.0, 0.0])
        self.assertEqual(
            captured["url"],
            "https://fxmacrodata.com/api/v1/forex/eur/usd"
            "?start_date=2024-01-01&end_date=2024-01-31",
        )
        self.assertEqual(captured["accept"], "application/json")
        self.assertEqual(captured["timeout"], 12)

    @patch.dict("os.environ", {"FXMACRODATA_API_KEY": "test-key"})
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.fxmacrodata.urlopen"
    )
    def test_includes_environment_api_key(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            json.dumps({"data": [{"date": "2024-01-01", "val": 1.1038}]})
        )
        provider = FXMacroDataOHLCVDataProvider(
            symbol="EUR/USD",
            market="FXMACRODATA",
            time_frame="1d",
        )
        provider.get_data(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        request = mock_urlopen.call_args[0][0]
        self.assertIn("api_key=test-key", request.full_url)

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.fxmacrodata.urlopen"
    )
    def test_get_data_returns_pandas_when_configured(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            json.dumps({"data": [{"date": "2024-01-01", "val": 1.1038}]})
        )
        provider = FXMacroDataOHLCVDataProvider(
            symbol="EURUSD",
            market="FXMACRODATA",
            time_frame="1d",
            pandas=True,
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pd.DataFrame)


class TestFXMacroDataCopy(TestCase):
    def test_copy_creates_new_instance(self):
        provider = FXMacroDataOHLCVDataProvider()
        data_source = DataSource(
            identifier="eurusd_daily",
            market="FXMACRODATA",
            symbol="EURUSD",
            data_type="OHLCV",
            time_frame="1d",
        )
        copied = provider.copy(data_source)
        self.assertIsInstance(copied, FXMacroDataOHLCVDataProvider)
        self.assertEqual(copied.symbol, "EURUSD")
        self.assertEqual(copied.market, "FXMACRODATA")
        self.assertIsNot(provider, copied)


class TestFXMacroDataRegistration(TestCase):
    def test_in_default_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_data_providers

        providers = get_default_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, FXMacroDataOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)

    def test_in_default_ohlcv_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_ohlcv_data_providers

        providers = get_default_ohlcv_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, FXMacroDataOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)
