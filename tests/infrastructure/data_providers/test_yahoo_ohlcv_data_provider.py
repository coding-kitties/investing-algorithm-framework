import os
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch, MagicMock

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import DataType, DataSource
from investing_algorithm_framework.infrastructure import \
    YahooOHLCVDataProvider


def _make_ohlcv_pandas_df(rows=5):
    """Create a sample pandas OHLCV DataFrame like yfinance returns."""
    dates = pd.date_range(
        start="2024-01-02", periods=rows, freq="D", tz="UTC"
    )
    return pd.DataFrame({
        "Date": dates,
        "Open": [100.0 + i for i in range(rows)],
        "High": [105.0 + i for i in range(rows)],
        "Low": [95.0 + i for i in range(rows)],
        "Close": [102.0 + i for i in range(rows)],
        "Volume": [1000000 + i * 100 for i in range(rows)],
    }).set_index("Date")


class TestYahooOHLCVDataProviderHasData(TestCase):
    """Test the has_data matching logic."""

    def test_returns_false_for_non_yahoo_market(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="btc_ohlcv",
            market="BITVAVO",
            symbol="BTC/EUR",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_non_ohlcv_type(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ticker",
            market="YAHOO",
            symbol="AAPL",
            data_type="TICKER",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.yahoo._ensure_yfinance"
    )
    def test_returns_true_for_valid_yahoo_symbol(self, mock_yf):
        ticker_mock = MagicMock()
        ticker_mock.info = {"symbol": "AAPL"}
        mock_yf.return_value.Ticker.return_value = ticker_mock

        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="YAHOO",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.yahoo._ensure_yfinance"
    )
    def test_returns_false_for_invalid_yahoo_symbol(self, mock_yf):
        ticker_mock = MagicMock()
        ticker_mock.info = {}
        mock_yf.return_value.Ticker.return_value = ticker_mock

        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="fake_ohlcv",
            market="YAHOO",
            symbol="NOTREAL123",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_when_market_is_none(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))


class TestYahooOHLCVDataProviderGetData(TestCase):
    """Test the get_data method with mocked yfinance."""

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.yahoo.YahooOHLCVDataProvider._download_ohlcv"
    )
    def test_get_data_returns_polars_dataframe(self, mock_download):
        sample_df = _make_ohlcv_pandas_df()
        sample_df = sample_df.reset_index()
        sample_df = sample_df.rename(columns={"Date": "Datetime"})
        mock_download.return_value = pl.from_pandas(
            sample_df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        provider = YahooOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="YAHOO",
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
        self.assertEqual(len(data), 5)

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.yahoo.YahooOHLCVDataProvider._download_ohlcv"
    )
    def test_get_data_returns_pandas_when_configured(self, mock_download):
        sample_df = _make_ohlcv_pandas_df()
        sample_df = sample_df.reset_index()
        sample_df = sample_df.rename(columns={"Date": "Datetime"})
        mock_download.return_value = pl.from_pandas(
            sample_df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        provider = YahooOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="YAHOO",
            pandas=True,
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )
        self.assertIsInstance(data, pd.DataFrame)


class TestYahooOHLCVDataProviderCopy(TestCase):
    """Test the copy method."""

    def test_copy_creates_new_instance(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="YAHOO",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        copied = provider.copy(data_source)
        self.assertIsInstance(copied, YahooOHLCVDataProvider)
        self.assertEqual(copied.symbol, "AAPL")
        self.assertEqual(copied.market, "YAHOO")
        self.assertIsNot(provider, copied)

    def test_copy_raises_without_symbol(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="YAHOO",
            data_type="OHLCV",
            time_frame="1d",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)

    def test_copy_raises_without_time_frame(self):
        provider = YahooOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="YAHOO",
            symbol="AAPL",
            data_type="OHLCV",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)


class TestYahooOHLCVDataProviderTimeFrame(TestCase):
    """Test time frame mapping."""

    def test_supported_timeframes(self):
        for tf in ["1m", "2m", "5m", "15m", "30m", "1h", "1d", "1W", "1M"]:
            provider = YahooOHLCVDataProvider(time_frame=tf)
            interval = provider._get_provider_interval()
            self.assertIsNotNone(interval)

    def test_unsupported_timeframe_raises(self):
        provider = YahooOHLCVDataProvider(time_frame="3d")
        with self.assertRaises(Exception) as cm:
            provider._get_provider_interval()
        self.assertIn("not supported", str(cm.exception))


class TestYahooOHLCVDataProviderRegistration(TestCase):
    """Test that Yahoo provider is registered as a default provider."""

    def test_in_default_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_data_providers
        providers = get_default_data_providers()
        yahoo_providers = [
            p for p in providers
            if isinstance(p, YahooOHLCVDataProvider)
        ]
        self.assertEqual(len(yahoo_providers), 1)

    def test_in_default_ohlcv_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_ohlcv_data_providers
        providers = get_default_ohlcv_data_providers()
        yahoo_providers = [
            p for p in providers
            if isinstance(p, YahooOHLCVDataProvider)
        ]
        self.assertEqual(len(yahoo_providers), 1)
