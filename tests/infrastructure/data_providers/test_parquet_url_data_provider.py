import io
import unittest
from unittest.mock import patch, MagicMock

import polars as pl

from investing_algorithm_framework import DataSource, ParquetURLDataProvider


MOCK_TARGET = (
    "investing_algorithm_framework.infrastructure.data_providers"
    ".base_url.urllib.request.urlopen"
)


def _make_parquet_bytes(df):
    """Helper to serialize a Polars DataFrame to Parquet bytes."""
    buf = io.BytesIO()
    df.write_parquet(buf)
    return buf.getvalue()


class TestDataSourceFromParquet(unittest.TestCase):
    """Tests for the DataSource.from_parquet() class method."""

    def test_from_parquet_creates_data_source(self):
        ds = DataSource.from_parquet(
            identifier="features",
            url="https://storage.example.com/features.parquet",
            date_column="date",
        )
        self.assertEqual(ds.identifier, "features")
        self.assertEqual(
            ds.url, "https://storage.example.com/features.parquet"
        )
        self.assertEqual(ds.date_column, "date")
        self.assertEqual(
            ds.data_provider_identifier, "parquet_url_data_provider"
        )
        self.assertTrue(ds.cache)

    def test_from_parquet_defaults(self):
        ds = DataSource.from_parquet(
            identifier="test",
            url="https://example.com/test.parquet",
        )
        self.assertIsNone(ds.date_column)
        self.assertIsNone(ds.date_format)
        self.assertTrue(ds.cache)
        self.assertIsNone(ds.refresh_interval)
        self.assertIsNone(ds.post_process)

    def test_from_parquet_no_pre_process(self):
        """from_parquet should not accept pre_process."""
        # Parquet is binary, pre_process (text-based) is not supported
        import inspect
        sig = inspect.signature(DataSource.from_parquet)
        self.assertNotIn("pre_process", sig.parameters)


class TestParquetURLDataProvider(unittest.TestCase):
    """Tests for ParquetURLDataProvider."""

    SAMPLE_DF = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "symbol": ["BTC", "BTC"],
        "score": [0.8, 0.6],
    })

    def _mock_urlopen(self, df=None):
        if df is None:
            df = self.SAMPLE_DF
        parquet_bytes = _make_parquet_bytes(df)
        response = MagicMock()
        response.read.return_value = parquet_bytes
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        return response

    def test_has_data_matches_parquet_url_data_source(self):
        provider = ParquetURLDataProvider()
        ds = DataSource.from_parquet(
            identifier="test",
            url="https://example.com/test.parquet",
        )
        self.assertTrue(provider.has_data(ds))

    def test_has_data_rejects_csv_provider(self):
        provider = ParquetURLDataProvider()
        ds = DataSource.from_csv(
            identifier="test",
            url="https://example.com/test.csv",
        )
        self.assertFalse(provider.has_data(ds))

    @patch(MOCK_TARGET)
    def test_get_data_fetches_and_parses_parquet(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = ParquetURLDataProvider(
            url="https://example.com/data.parquet",
            cache=False,
        )

        df = provider.get_data()
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertIn("date", df.columns)
        self.assertIn("symbol", df.columns)
        self.assertIn("score", df.columns)

    @patch(MOCK_TARGET)
    def test_get_data_with_post_process(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        def add_column(df):
            return df.with_columns(
                (pl.col("score") * 100).alias("score_pct")
            )

        provider = ParquetURLDataProvider(
            url="https://example.com/data.parquet",
            post_process=add_column,
            cache=False,
        )

        df = provider.get_data()
        self.assertIn("score_pct", df.columns)

    @patch(MOCK_TARGET)
    def test_caching_does_not_refetch(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = ParquetURLDataProvider(
            url="https://example.com/data.parquet",
            cache=True,
        )
        # Disable file-based cache to isolate in-memory caching
        provider._get_cache_path = lambda: None

        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_copy_preserves_config(self):
        provider = ParquetURLDataProvider(
            url="https://example.com/data.parquet",
            date_column="date",
            cache=True,
        )

        copied = provider.copy()
        self.assertEqual(
            copied._url, "https://example.com/data.parquet"
        )
        self.assertEqual(copied._date_column, "date")
        self.assertIsInstance(copied, ParquetURLDataProvider)

    def test_raises_on_missing_url(self):
        provider = ParquetURLDataProvider(cache=False)
        with self.assertRaises(ValueError):
            provider.get_data()

    @patch(MOCK_TARGET)
    def test_prepare_backtest_data(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = ParquetURLDataProvider(
            url="https://example.com/data.parquet",
            cache=False,
        )

        from datetime import datetime, timezone
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        provider.prepare_backtest_data(start, end)
        self.assertIsNotNone(provider._cached_data)


if __name__ == "__main__":
    unittest.main()
