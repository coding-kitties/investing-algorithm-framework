import os
from datetime import datetime, timedelta
from unittest import TestCase

from investing_algorithm_framework.infrastructure import \
    CSVOHLCVMarketDataSource


class Test(TestCase):

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

    def test_right_columns(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}"
        )

    def test_start_date(self):
        start_date = datetime(2023, 12, 1)
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}"
        )
        self.assertEqual(
            start_date,
            csv_ohlcv_market_data_source.start_date.replace(microsecond=0),
        )

    def test_end_date(self):
        end_date = datetime(2023, 12, 25)
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}"
        )
        self.assertEqual(
            end_date,
            csv_ohlcv_market_data_source.end_date.replace(microsecond=0),
        )

    def test_empty(self):
        start_date = datetime(2023, 12, 1)
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}"
        )
        self.assertFalse(data_source.empty())
        self.assertEqual(start_date, data_source.start_date)
        data_source.start_date = datetime(2023, 12, 25)
        data_source.end_date = datetime(2023, 12, 16)
        self.assertTrue(data_source.empty())

    def test_get_data(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}"
        )
        number_of_runs = 0

        while not datasource.empty():
            data = datasource.get_data()
            datasource.start_date = datasource.start_date + timedelta(days=1)
            datasource.end_date = datasource.end_date + timedelta(days=1)
            self.assertTrue(len(data) > 0)
            number_of_runs += 1

        self.assertTrue(number_of_runs > 0)

    def test_get_identifier(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            identifier="test"
        )
        self.assertEqual("test", datasource.get_identifier())

    def test_get_market(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            market="test"
        )
        self.assertEqual("test", datasource.get_market())

    def test_get_symbol(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            symbol="BTC/EUR"
        )
        self.assertEqual("BTC/EUR", datasource.get_symbol())

    def test_get_timeframe(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_15m_2023-12-" \
                    "01:00:00_2023-12-25:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            timeframe="15m"
        )
        self.assertEqual("15m", datasource.get_timeframe())
