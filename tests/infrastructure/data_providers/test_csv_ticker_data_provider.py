import os
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import DataSource
from investing_algorithm_framework.infrastructure import \
    CSVTickerDataProvider


class TestCSVTickerDataProvider(TestCase):
    """
    Test cases for the CSVTickerDataProvider class.
    """

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.file_name = \
            "TICKER_BTC-EUR_BINANCE" \
            "_2023-08-23-22-00_2023-12-02-00-00.csv"
        self.storage_path = os.path.join(
            self.resource_dir, "test_data", "ohlcv",
            self.file_name
        )

    def test_basic_loading(self):
        """CSVTickerDataProvider loads a CSV file without error."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        self.assertIsNotNone(data_provider)

    def test_has_data_matching(self):
        """has_data returns True for matching TICKER DataSource."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            data_type="TICKER",
        )
        self.assertTrue(
            data_provider.has_data(
                data_source,
                start_date=datetime(
                    2023, 8, 24, 0, 0, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=timezone.utc
                )
            )
        )

    def test_has_data_wrong_symbol(self):
        """has_data returns False for mismatched symbol."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        data_source = DataSource(
            market="binance",
            symbol="ETH/EUR",
            data_type="TICKER",
        )
        self.assertFalse(
            data_provider.has_data(
                data_source,
                start_date=datetime(
                    2023, 8, 24, 0, 0, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=timezone.utc
                )
            )
        )

    def test_has_data_wrong_market(self):
        """has_data returns False for mismatched market."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        data_source = DataSource(
            market="bitvavo",
            symbol="BTC/EUR",
            data_type="TICKER",
        )
        self.assertFalse(
            data_provider.has_data(
                data_source,
                start_date=datetime(
                    2023, 8, 24, 0, 0, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=timezone.utc
                )
            )
        )

    def test_has_data_wrong_data_type(self):
        """has_data returns False for OHLCV data type."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            data_type="OHLCV",
            time_frame="2h",
        )
        self.assertFalse(
            data_provider.has_data(
                data_source,
                start_date=datetime(
                    2023, 8, 24, 0, 0, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=timezone.utc
                )
            )
        )

    def test_get_data(self):
        """get_data returns a ticker dict with correct keys."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
        )
        result = data_provider.get_data(
            date=datetime(
                2023, 9, 15, 0, 0, tzinfo=timezone.utc
            )
        )
        self.assertIsInstance(result, dict)
        expected_keys = [
            "symbol", "market", "datetime",
            "high", "low", "bid", "ask",
            "open", "close", "last", "volume"
        ]
        for key in expected_keys:
            self.assertIn(key, result)
        self.assertEqual(result["symbol"], "BTC/EUR")
        self.assertEqual(result["market"], "BINANCE")

    def test_get_identifier(self):
        """Custom identifier is preserved."""
        data_provider = CSVTickerDataProvider(
            storage_path=self.storage_path,
            market="binance",
            symbol="BTC/EUR",
            data_provider_identifier="my_custom_ticker",
        )
        self.assertEqual(
            "my_custom_ticker",
            data_provider.data_provider_identifier
        )
