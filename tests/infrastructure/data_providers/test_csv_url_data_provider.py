import unittest
from unittest.mock import patch, MagicMock

import polars as pl

from investing_algorithm_framework import DataSource, CSVURLDataProvider


MOCK_TARGET = (
    "investing_algorithm_framework.infrastructure.data_providers"
    ".base_url.urllib.request.urlopen"
)


class TestDataSourceFromCsv(unittest.TestCase):
    """Tests for the DataSource.from_csv() class method."""

    def test_from_csv_creates_data_source(self):
        """Test that from_csv creates a properly configured DataSource."""
        ds = DataSource.from_csv(
            identifier="sentiment",
            url="https://example.com/data.csv",
            date_column="date",
            date_format="%Y-%m-%d",
        )
        self.assertEqual(ds.identifier, "sentiment")
        self.assertEqual(ds.url, "https://example.com/data.csv")
        self.assertEqual(ds.date_column, "date")
        self.assertEqual(ds.date_format, "%Y-%m-%d")
        self.assertEqual(
            ds.data_provider_identifier, "csv_url_data_provider"
        )
        self.assertTrue(ds.cache)

    def test_from_csv_with_all_options(self):
        """Test from_csv with all optional parameters."""
        pre = lambda x: x  # noqa: E731
        post = lambda x: x  # noqa: E731

        ds = DataSource.from_csv(
            identifier="earnings",
            url="https://example.com/earnings.csv",
            date_column="report_date",
            date_format="%m/%d/%Y",
            cache=False,
            refresh_interval="1d",
            pre_process=pre,
            post_process=post,
        )
        self.assertEqual(ds.identifier, "earnings")
        self.assertEqual(ds.url, "https://example.com/earnings.csv")
        self.assertFalse(ds.cache)
        self.assertEqual(ds.refresh_interval, "1d")
        self.assertEqual(ds.pre_process, pre)
        self.assertEqual(ds.post_process, post)

    def test_from_csv_get_identifier(self):
        """Test that the identifier is returned correctly."""
        ds = DataSource.from_csv(
            identifier="my_data",
            url="https://example.com/data.csv",
        )
        self.assertEqual(ds.get_identifier(), "my_data")

    def test_from_csv_defaults(self):
        """Test default values for optional parameters."""
        ds = DataSource.from_csv(
            identifier="test",
            url="https://example.com/test.csv",
        )
        self.assertIsNone(ds.date_column)
        self.assertIsNone(ds.date_format)
        self.assertTrue(ds.cache)
        self.assertIsNone(ds.refresh_interval)
        self.assertIsNone(ds.pre_process)
        self.assertIsNone(ds.post_process)


class TestCSVURLDataProvider(unittest.TestCase):
    """Tests for CSVURLDataProvider."""

    CSV_CONTENT = "date,symbol,score\n2024-01-01,BTC,0.8\n2024-01-02,BTC,0.6"

    def _mock_urlopen(self, csv_text=None):
        """Create a mock for urllib.request.urlopen."""
        if csv_text is None:
            csv_text = self.CSV_CONTENT
        response = MagicMock()
        response.read.return_value = csv_text.encode("utf-8")
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        return response

    def test_has_data_matches_csv_url_data_source(self):
        """Test that has_data returns True for matching DataSources."""
        provider = CSVURLDataProvider()
        ds = DataSource.from_csv(
            identifier="test",
            url="https://example.com/test.csv",
        )
        self.assertTrue(provider.has_data(ds))

    def test_has_data_rejects_non_csv_url(self):
        """Test that has_data returns False for non-CSV URL DataSources."""
        provider = CSVURLDataProvider()
        ds = DataSource(
            identifier="test",
            data_type="OHLCV",
            symbol="BTC/EUR",
            market="BITVAVO",
        )
        self.assertFalse(provider.has_data(ds))

    def test_has_data_rejects_no_url(self):
        """Test that has_data returns False when no URL is set."""
        provider = CSVURLDataProvider()
        ds = DataSource(
            identifier="test",
            data_type="CUSTOM",
            data_provider_identifier="csv_url_data_provider",
        )
        self.assertFalse(provider.has_data(ds))

    @patch(MOCK_TARGET)
    def test_get_data_fetches_and_parses_csv(self, mock_urlopen):
        """Test that get_data fetches and parses CSV correctly."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            cache=False,
        )

        df = provider.get_data()
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertIn("date", df.columns)
        self.assertIn("symbol", df.columns)
        self.assertIn("score", df.columns)

    @patch(MOCK_TARGET)
    def test_get_data_with_date_parsing(self, mock_urlopen):
        """Test date column parsing."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            date_column="date",
            date_format="%Y-%m-%d",
            cache=False,
        )

        df = provider.get_data()
        self.assertEqual(df["date"].dtype, pl.Datetime)

    @patch(MOCK_TARGET)
    def test_get_data_with_pre_process(self, mock_urlopen):
        """Test pre-processing callback."""
        mock_urlopen.return_value = self._mock_urlopen()

        def add_header_comment(text):
            # Remove any comment lines
            lines = [line for line in text.split("\n") if not line.startswith("#")]
            return "\n".join(lines)

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            pre_process=add_header_comment,
            cache=False,
        )

        df = provider.get_data()
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(len(df), 2)

    @patch(MOCK_TARGET)
    def test_get_data_with_post_process(self, mock_urlopen):
        """Test post-processing callback."""
        mock_urlopen.return_value = self._mock_urlopen()

        def add_column(df):
            return df.with_columns(
                (pl.col("score") * 100).alias("score_pct")
            )

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            post_process=add_column,
            cache=False,
        )

        df = provider.get_data()
        self.assertIn("score_pct", df.columns)
        self.assertAlmostEqual(df["score_pct"][0], 80.0)

    @patch(MOCK_TARGET)
    def test_caching_does_not_refetch(self, mock_urlopen):
        """Test that cached data is reused without re-fetching."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            cache=True,
        )
        # Disable file-based cache to isolate in-memory caching
        provider._get_cache_path = lambda: None

        # First call fetches
        df1 = provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

        # Second call uses cache
        df2 = provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

        self.assertEqual(len(df1), len(df2))

    @patch(MOCK_TARGET)
    def test_no_cache_refetches(self, mock_urlopen):
        """Test that disabling cache causes re-fetching."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            cache=False,
        )

        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

        # Re-create mock for second call
        mock_urlopen.return_value = self._mock_urlopen()
        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_copy_preserves_config(self):
        """Test that copy() preserves provider configuration."""
        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            date_column="date",
            date_format="%Y-%m-%d",
            cache=True,
            refresh_interval="1d",
        )

        copied = provider.copy()
        self.assertEqual(copied._url, "https://example.com/data.csv")
        self.assertEqual(copied._date_column, "date")
        self.assertEqual(copied._date_format, "%Y-%m-%d")
        self.assertTrue(copied._cache)
        self.assertEqual(copied._refresh_interval, "1d")

    def test_copy_with_data_source_overrides(self):
        """Test that copy() uses data source values when available."""
        provider = CSVURLDataProvider(
            url="https://example.com/default.csv",
        )

        ds = DataSource.from_csv(
            identifier="test",
            url="https://example.com/override.csv",
            date_column="my_date",
        )

        copied = provider.copy(data_source=ds)
        self.assertEqual(copied._url, "https://example.com/override.csv")
        self.assertEqual(copied._date_column, "my_date")

    def test_raises_on_missing_url(self):
        """Test that fetching without a URL raises ValueError."""
        provider = CSVURLDataProvider(cache=False)

        with self.assertRaises(ValueError):
            provider.get_data()

    @patch(MOCK_TARGET)
    def test_prepare_backtest_data(self, mock_urlopen):
        """Test that prepare_backtest_data pre-fetches the data."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            cache=False,
        )

        from datetime import datetime, timezone
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        provider.prepare_backtest_data(start, end)
        self.assertIsNotNone(provider._cached_data)

    @patch(MOCK_TARGET)
    def test_get_backtest_data_returns_data(self, mock_urlopen):
        """Test that get_backtest_data returns cached data."""
        mock_urlopen.return_value = self._mock_urlopen()

        provider = CSVURLDataProvider(
            url="https://example.com/data.csv",
            cache=False,
        )

        from datetime import datetime, timezone
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        provider.prepare_backtest_data(start, end)
        df = provider.get_backtest_data(
            backtest_index_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            backtest_start_date=start,
            backtest_end_date=end,
        )
        self.assertIsInstance(df, pl.DataFrame)


if __name__ == "__main__":
    unittest.main()
