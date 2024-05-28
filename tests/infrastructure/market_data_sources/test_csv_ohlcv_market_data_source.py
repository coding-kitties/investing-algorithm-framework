import os
from datetime import datetime, timedelta
from unittest import TestCase

from dateutil import parser
from dateutil.tz import tzutc
from polars import DataFrame

from investing_algorithm_framework.domain import OperationalException, \
    TimeFrame, DATETIME_FORMAT
from investing_algorithm_framework.infrastructure import \
    CSVOHLCVMarketDataSource


class Test(TestCase):
    """
    Test cases for the CSVOHLCVMarketDataSource class.
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

    def test_right_columns(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/market_data_sources/"
                          f"{file_name}",
        )
        df = data_source.get_data()
        self.assertEqual(
            ["Datetime", "Open", "High", "Low", "Close", "Volume"], df.columns
        )

    def test_throw_exception_when_missing_column_names_columns(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_2h_NO_COLUMNS_2023-" \
                    "08-07:07:59_2023-12-02:00:00.csv"

        with self.assertRaises(OperationalException):
            CSVOHLCVMarketDataSource(
                csv_file_path=f"{self.resource_dir}/"
                              "market_data_sources_for_testing/"
                              f"{file_name}",
                window_size=10
            )

    def test_start_date(self):
        start_date = datetime(2023, 8, 7, 8, 0, tzinfo=tzutc())
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=10,
            timeframe=TimeFrame.TWO_HOUR,
        )
        self.assertEqual(
            start_date,
            csv_ohlcv_market_data_source.start_date.replace(microsecond=0),
        )

    def test_start_date_with_window_size(self):
        start_date = datetime(
            year=2023, month=8, day=7, hour=10, minute=0, tzinfo=tzutc()
        )
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=12,
            timeframe=TimeFrame.TWO_HOUR,
        )
        data = csv_ohlcv_market_data_source.get_data(start_date=start_date)
        self.assertEqual(12, len(data))
        first_date = parser.parse(data["Datetime"][0])
        self.assertEqual(
            start_date.strftime(DATETIME_FORMAT),
            first_date.strftime(DATETIME_FORMAT)
        )

    def test_start_date_with_backtest_index_date(self):
        start_date = datetime(2023, 8, 7, 8, 0, tzinfo=tzutc())
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=10,
            timeframe=TimeFrame.TWO_HOUR,
        )
        data = csv_ohlcv_market_data_source.get_data(
            backtest_index_date=datetime(2023, 8, 7, 8, 0, tzinfo=tzutc())
        )
        self.assertEqual(10, len(data))
        first_date = parser.parse(data["Datetime"][0])
        self.assertEqual(
            start_date.strftime(DATETIME_FORMAT),
            first_date.strftime(DATETIME_FORMAT)
        )

    def test_end_date(self):
        end_date = datetime(2023, 12, 2, 0, 0, tzinfo=tzutc())
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
        )
        self.assertEqual(
            end_date,
            csv_ohlcv_market_data_source.end_date.replace(microsecond=0),
        )

    def test_empty(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        data_source = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=10,
            timeframe="2h",
        )
        start_date = datetime(2023, 8, 7, 8, 0, tzinfo=tzutc())
        end_date = datetime(2023, 12, 2, 0, 0, tzinfo=tzutc())
        self.assertFalse(data_source.empty(start_date, end_date))

    def test_get_data(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=200,
            timeframe="2h",
        )
        number_of_runs = 0
        backtest_index_date = datasource.start_date

        while not datasource.empty():
            data = datasource.get_data(backtest_index_date=backtest_index_date)
            backtest_index_date = parser.parse(data["Datetime"][-1])
            self.assertTrue(len(data) > 0)
            self.assertTrue(isinstance(data, DataFrame))
            number_of_runs += 1

        self.assertTrue(number_of_runs > 0)

    def test_get_identifier(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            identifier="test",
            window_size=10,
            timeframe="2h",
        )
        self.assertEqual("test", datasource.get_identifier())

    def test_get_market(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            market="test",
            timeframe="2h",
        )
        self.assertEqual("test", datasource.get_market())

    def test_get_symbol(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            symbol="BTC/EUR",
            window_size=10,
            timeframe="2h",
        )
        self.assertEqual("BTC/EUR", datasource.get_symbol())

    def test_get_timeframe(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07:07:59_2023-12-02:00:00.csv"
        datasource = CSVOHLCVMarketDataSource(
            csv_file_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            timeframe="2h",
            window_size=10,
        )
        self.assertEqual("2h", datasource.get_timeframe())
