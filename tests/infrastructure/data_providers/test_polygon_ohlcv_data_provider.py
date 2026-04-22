from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch, MagicMock

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import DataType, DataSource
from investing_algorithm_framework.infrastructure import \
    PolygonOHLCVDataProvider


def _make_polygon_polars_df(rows=5):
    """Create a sample Polars OHLCV DataFrame."""
    from datetime import timedelta
    base = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return pl.DataFrame({
        "Datetime": [base + timedelta(days=i) for i in range(rows)],
        "Open": [100.0 + i for i in range(rows)],
        "High": [105.0 + i for i in range(rows)],
        "Low": [95.0 + i for i in range(rows)],
        "Close": [102.0 + i for i in range(rows)],
        "Volume": [1000000.0 + i * 100 for i in range(rows)],
    })


class TestPolygonHasData(TestCase):
    """Test the has_data matching logic."""

    def test_returns_false_for_non_polygon_market(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="btc_ohlcv",
            market="BITVAVO",
            symbol="BTC/EUR",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_non_ohlcv_type(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ticker",
            market="POLYGON",
            symbol="AAPL",
            data_type="TICKER",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_true_for_valid_polygon_source(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="POLYGON",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    def test_returns_true_case_insensitive(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="polygon",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    def test_returns_false_when_market_is_none(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_unsupported_timeframe(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="POLYGON",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="2m",
        )
        self.assertFalse(provider.has_data(data_source))


class TestPolygonGetData(TestCase):
    """Test the get_data method with mocked polygon."""

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.polygon"
        ".PolygonOHLCVDataProvider._download_ohlcv"
    )
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.polygon"
        ".PolygonOHLCVDataProvider._get_api_key"
    )
    def test_get_data_returns_polars_dataframe(
        self, mock_api_key, mock_download
    ):
        mock_api_key.return_value = "test_key"
        mock_download.return_value = _make_polygon_polars_df()

        provider = PolygonOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="POLYGON",
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )
        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(
            data.columns,
            ["Datetime", "Open", "High", "Low", "Close", "Volume"],
        )

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.polygon"
        ".PolygonOHLCVDataProvider._download_ohlcv"
    )
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.polygon"
        ".PolygonOHLCVDataProvider._get_api_key"
    )
    def test_get_data_returns_pandas_when_configured(
        self, mock_api_key, mock_download
    ):
        mock_api_key.return_value = "test_key"
        mock_download.return_value = _make_polygon_polars_df()

        provider = PolygonOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="POLYGON",
            pandas=True,
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )
        self.assertIsInstance(data, pd.DataFrame)


class TestPolygonCopy(TestCase):
    """Test the copy method."""

    def test_copy_creates_new_instance(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="POLYGON",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        copied = provider.copy(data_source)
        self.assertIsInstance(copied, PolygonOHLCVDataProvider)
        self.assertEqual(copied.symbol, "AAPL")
        self.assertEqual(copied.market, "POLYGON")
        self.assertIsNot(provider, copied)

    def test_copy_raises_without_symbol(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="POLYGON",
            data_type="OHLCV",
            time_frame="1d",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)

    def test_copy_raises_without_time_frame(self):
        provider = PolygonOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="POLYGON",
            symbol="AAPL",
            data_type="OHLCV",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)


class TestPolygonTimeFrame(TestCase):
    """Test time frame mapping."""

    def test_supported_timeframes(self):
        for tf in ["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M"]:
            provider = PolygonOHLCVDataProvider(time_frame=tf)
            config = provider._get_polygon_config()
            self.assertIsNotNone(config)

    def test_unsupported_timeframe_raises(self):
        provider = PolygonOHLCVDataProvider(time_frame="2m")
        with self.assertRaises(Exception) as cm:
            provider._get_polygon_config()
        self.assertIn("not supported", str(cm.exception))


class TestPolygonApiKey(TestCase):
    """Test API key requirement."""

    def test_raises_without_api_key(self):
        provider = PolygonOHLCVDataProvider()
        with self.assertRaises(Exception) as cm:
            provider._get_api_key()
        self.assertIn("API key", str(cm.exception))


class TestPolygonRegistration(TestCase):
    """Test that provider is registered as a default provider."""

    def test_in_default_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_data_providers
        providers = get_default_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, PolygonOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)

    def test_in_default_ohlcv_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_ohlcv_data_providers
        providers = get_default_ohlcv_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, PolygonOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)
