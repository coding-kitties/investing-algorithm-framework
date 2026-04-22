from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch, MagicMock

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import DataType, DataSource
from investing_algorithm_framework.infrastructure import \
    AlphaVantageOHLCVDataProvider


def _make_av_pandas_df(rows=5):
    """Create a sample pandas OHLCV DataFrame like alpha_vantage returns."""
    dates = pd.date_range(
        start="2024-01-02", periods=rows, freq="D", tz="UTC"
    )
    return pd.DataFrame({
        "date": dates,
        "1. open": [100.0 + i for i in range(rows)],
        "2. high": [105.0 + i for i in range(rows)],
        "3. low": [95.0 + i for i in range(rows)],
        "4. close": [102.0 + i for i in range(rows)],
        "5. volume": [1000000 + i * 100 for i in range(rows)],
    }).set_index("date")


class TestAlphaVantageHasData(TestCase):
    """Test the has_data matching logic."""

    def test_returns_false_for_non_alpha_vantage_market(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="btc_ohlcv",
            market="BITVAVO",
            symbol="BTC/EUR",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_non_ohlcv_type(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ticker",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="TICKER",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_true_for_valid_alpha_vantage_source(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    def test_returns_true_case_insensitive(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="alpha_vantage",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertTrue(provider.has_data(data_source))

    def test_returns_false_when_market_is_none(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        self.assertFalse(provider.has_data(data_source))

    def test_returns_false_for_unsupported_timeframe(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="2m",
        )
        self.assertFalse(provider.has_data(data_source))


class TestAlphaVantageGetData(TestCase):
    """Test the get_data method with mocked alpha_vantage."""

    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.alpha_vantage"
        ".AlphaVantageOHLCVDataProvider._download_ohlcv"
    )
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.alpha_vantage"
        ".AlphaVantageOHLCVDataProvider._get_api_key"
    )
    def test_get_data_returns_polars_dataframe(
        self, mock_api_key, mock_download
    ):
        mock_api_key.return_value = "test_key"
        sample_df = _make_av_pandas_df()
        sample_df = sample_df.reset_index()
        sample_df = sample_df.rename(columns={
            "date": "Datetime",
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume",
        })
        mock_download.return_value = pl.from_pandas(
            sample_df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        provider = AlphaVantageOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="ALPHA_VANTAGE",
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
        ".data_providers.alpha_vantage"
        ".AlphaVantageOHLCVDataProvider._download_ohlcv"
    )
    @patch(
        "investing_algorithm_framework.infrastructure"
        ".data_providers.alpha_vantage"
        ".AlphaVantageOHLCVDataProvider._get_api_key"
    )
    def test_get_data_returns_pandas_when_configured(
        self, mock_api_key, mock_download
    ):
        mock_api_key.return_value = "test_key"
        sample_df = _make_av_pandas_df()
        sample_df = sample_df.reset_index()
        sample_df = sample_df.rename(columns={
            "date": "Datetime",
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume",
        })
        mock_download.return_value = pl.from_pandas(
            sample_df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        provider = AlphaVantageOHLCVDataProvider(
            symbol="AAPL",
            time_frame="1d",
            market="ALPHA_VANTAGE",
            pandas=True,
        )
        data = provider.get_data(
            start_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )
        self.assertIsInstance(data, pd.DataFrame)


class TestAlphaVantageCopy(TestCase):
    """Test the copy method."""

    def test_copy_creates_new_instance(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="aapl_ohlcv",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
        copied = provider.copy(data_source)
        self.assertIsInstance(copied, AlphaVantageOHLCVDataProvider)
        self.assertEqual(copied.symbol, "AAPL")
        self.assertEqual(copied.market, "ALPHA_VANTAGE")
        self.assertIsNot(provider, copied)

    def test_copy_raises_without_symbol(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="ALPHA_VANTAGE",
            data_type="OHLCV",
            time_frame="1d",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)

    def test_copy_raises_without_time_frame(self):
        provider = AlphaVantageOHLCVDataProvider()
        data_source = DataSource(
            identifier="test",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="OHLCV",
        )
        with self.assertRaises(Exception):
            provider.copy(data_source)


class TestAlphaVantageTimeFrame(TestCase):
    """Test time frame mapping."""

    def test_supported_timeframes(self):
        for tf in ["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M"]:
            provider = AlphaVantageOHLCVDataProvider(time_frame=tf)
            config = provider._get_av_config()
            self.assertIsNotNone(config)

    def test_unsupported_timeframe_raises(self):
        provider = AlphaVantageOHLCVDataProvider(time_frame="2m")
        with self.assertRaises(Exception) as cm:
            provider._get_av_config()
        self.assertIn("not supported", str(cm.exception))


class TestAlphaVantageApiKey(TestCase):
    """Test API key requirement."""

    def test_raises_without_api_key(self):
        provider = AlphaVantageOHLCVDataProvider()
        with self.assertRaises(Exception) as cm:
            provider._get_api_key()
        self.assertIn("API key", str(cm.exception))


class TestAlphaVantageRegistration(TestCase):
    """Test that provider is registered as a default provider."""

    def test_in_default_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_data_providers
        providers = get_default_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, AlphaVantageOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)

    def test_in_default_ohlcv_data_providers(self):
        from investing_algorithm_framework.infrastructure.data_providers \
            import get_default_ohlcv_data_providers
        providers = get_default_ohlcv_data_providers()
        matching = [
            p for p in providers
            if isinstance(p, AlphaVantageOHLCVDataProvider)
        ]
        self.assertEqual(len(matching), 1)
