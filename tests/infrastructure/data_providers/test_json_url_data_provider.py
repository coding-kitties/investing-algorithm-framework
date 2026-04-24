import json
import unittest
from unittest.mock import patch, MagicMock

import polars as pl

from investing_algorithm_framework import DataSource, JSONURLDataProvider


MOCK_TARGET = (
    "investing_algorithm_framework.infrastructure.data_providers"
    ".base_url.urllib.request.urlopen"
)


class TestDataSourceFromJson(unittest.TestCase):
    """Tests for the DataSource.from_json() class method."""

    def test_from_json_creates_data_source(self):
        ds = DataSource.from_json(
            identifier="earnings",
            url="https://api.example.com/earnings.json",
            date_column="date",
            date_format="%Y-%m-%d",
        )
        self.assertEqual(ds.identifier, "earnings")
        self.assertEqual(ds.url, "https://api.example.com/earnings.json")
        self.assertEqual(ds.date_column, "date")
        self.assertEqual(ds.date_format, "%Y-%m-%d")
        self.assertEqual(
            ds.data_provider_identifier, "json_url_data_provider"
        )
        self.assertTrue(ds.cache)

    def test_from_json_defaults(self):
        ds = DataSource.from_json(
            identifier="test",
            url="https://example.com/test.json",
        )
        self.assertIsNone(ds.date_column)
        self.assertIsNone(ds.date_format)
        self.assertTrue(ds.cache)
        self.assertIsNone(ds.refresh_interval)
        self.assertIsNone(ds.pre_process)
        self.assertIsNone(ds.post_process)


class TestJSONURLDataProvider(unittest.TestCase):
    """Tests for JSONURLDataProvider."""

    JSON_RECORDS = [
        {"date": "2024-01-01", "symbol": "BTC", "score": 0.8},
        {"date": "2024-01-02", "symbol": "BTC", "score": 0.6},
    ]

    def _mock_urlopen(self, data=None):
        if data is None:
            data = self.JSON_RECORDS
        response = MagicMock()
        response.read.return_value = json.dumps(data).encode("utf-8")
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        return response

    def test_has_data_matches_json_url_data_source(self):
        provider = JSONURLDataProvider()
        ds = DataSource.from_json(
            identifier="test",
            url="https://example.com/test.json",
        )
        self.assertTrue(provider.has_data(ds))

    def test_has_data_rejects_non_json_url(self):
        provider = JSONURLDataProvider()
        ds = DataSource(
            identifier="test",
            data_type="OHLCV",
            symbol="BTC/EUR",
            market="BITVAVO",
        )
        self.assertFalse(provider.has_data(ds))

    def test_has_data_rejects_csv_provider(self):
        provider = JSONURLDataProvider()
        ds = DataSource.from_csv(
            identifier="test",
            url="https://example.com/test.csv",
        )
        self.assertFalse(provider.has_data(ds))

    @patch(MOCK_TARGET)
    def test_get_data_fetches_and_parses_json_records(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            cache=False,
        )

        df = provider.get_data()
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertIn("date", df.columns)
        self.assertIn("symbol", df.columns)
        self.assertIn("score", df.columns)

    @patch(MOCK_TARGET)
    def test_get_data_fetches_columnar_json(self, mock_urlopen):
        columnar = {
            "date": ["2024-01-01", "2024-01-02"],
            "symbol": ["BTC", "BTC"],
            "score": [0.8, 0.6],
        }
        mock_urlopen.return_value = self._mock_urlopen(columnar)

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            cache=False,
        )

        df = provider.get_data()
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(len(df), 2)

    @patch(MOCK_TARGET)
    def test_get_data_with_date_parsing(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            date_column="date",
            date_format="%Y-%m-%d",
            cache=False,
        )

        df = provider.get_data()
        self.assertEqual(df["date"].dtype, pl.Datetime)

    @patch(MOCK_TARGET)
    def test_get_data_with_post_process(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        def add_column(df):
            return df.with_columns(
                (pl.col("score") * 100).alias("score_pct")
            )

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            post_process=add_column,
            cache=False,
        )

        df = provider.get_data()
        self.assertIn("score_pct", df.columns)

    @patch(MOCK_TARGET)
    def test_caching_does_not_refetch(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            cache=True,
        )
        # Disable file-based cache to isolate in-memory caching
        provider._get_cache_path = lambda: None

        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

        provider.get_data()
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_copy_preserves_config(self):
        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            date_column="date",
            cache=True,
        )

        copied = provider.copy()
        self.assertEqual(copied._url, "https://example.com/data.json")
        self.assertEqual(copied._date_column, "date")
        self.assertIsInstance(copied, JSONURLDataProvider)

    def test_copy_with_data_source_overrides(self):
        provider = JSONURLDataProvider(
            url="https://example.com/default.json",
        )

        ds = DataSource.from_json(
            identifier="test",
            url="https://example.com/override.json",
            date_column="my_date",
        )

        copied = provider.copy(data_source=ds)
        self.assertEqual(
            copied._url, "https://example.com/override.json"
        )
        self.assertEqual(copied._date_column, "my_date")

    def test_raises_on_missing_url(self):
        provider = JSONURLDataProvider(cache=False)
        with self.assertRaises(ValueError):
            provider.get_data()

    @patch(MOCK_TARGET)
    def test_prepare_backtest_data(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen()

        provider = JSONURLDataProvider(
            url="https://example.com/data.json",
            cache=False,
        )

        from datetime import datetime, timezone
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        provider.prepare_backtest_data(start, end)
        self.assertIsNotNone(provider._cached_data)


if __name__ == "__main__":
    unittest.main()
