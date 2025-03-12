import os
from datetime import datetime
from unittest import TestCase

from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    BACKTEST_DATA_DIRECTORY_NAME, DATETIME_FORMAT
from investing_algorithm_framework.infrastructure import \
    CCXTOHLCVBacktestMarketDataSource


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

    def test_file_path(self):
        """
        Test if the file path is correct by defining a start and end date
        function that specify a window size of 200 candles of a 15-min
        timeframe (50 hours).

        Then take a backtest start date and end date that are multiple days
        apart and make sure that the file name is correct. The file name
        should be in the format:

        OHLCV_{symbol}_{market}_{timeframe}_{start_date_data}_
        {end_date_data}.csv

        Where the start date is the backtest start date minus 50 hours
        and the end date is the backtest end date.
        """
        correct_file_name = \
            "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv"
        data_source = CCXTOHLCVBacktestMarketDataSource(
            identifier="OHLCV_BTC_EUR_BINANCE_15m",
            market="BINANCE",
            symbol="BTC/EUR",
            time_frame="15m",
            window_size=200,
        )

        # The backtest start data should be 2023-12-15 00:00
        data_source.prepare_data(
            config={
                RESOURCE_DIRECTORY: self.resource_dir,
                BACKTEST_DATA_DIRECTORY_NAME: "market_data_sources_for_testing"
            },
            backtest_start_date=datetime(2023, 12, 17, 00, 00),
            backtest_end_date=datetime(2023, 12, 25, 00, 00),
        )
        self.assertEqual(correct_file_name, data_source.file_name)

    def test_window_size(self):
        correct_file_name = \
            "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv"
        data_source = CCXTOHLCVBacktestMarketDataSource(
            identifier="OHLCV_BTC_EUR_BINANCE_15m",
            market="BINANCE",
            symbol="BTC/EUR",
            time_frame="15m",
            window_size=200,
        )
        data_source.prepare_data(
            config={
                RESOURCE_DIRECTORY: self.resource_dir,
                BACKTEST_DATA_DIRECTORY_NAME: "market_data_sources_for_testing"
            },
            backtest_start_date=datetime(2023, 12, 17, 00, 00),
            backtest_end_date=datetime(2023, 12, 25, 00, 00),
        )

        self.assertEqual(correct_file_name, data_source.file_name)

    def test_right_columns(self):
        correct_file_name = \
            "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv"
        csv_file_path = f"{self.resource_dir}/market_data_sources_for_testing"\
                        f"/{correct_file_name}"
        data_source = CCXTOHLCVBacktestMarketDataSource(
            identifier="OHLCV_BTC_EUR_BINANCE_15m",
            market="BINANCE",
            symbol="BTC/EUR",
            time_frame="15m",
            window_size=200
        )
        data_source.config = {"DATETIME_FORMAT": DATETIME_FORMAT}
        data_source.prepare_data(
            config={
                RESOURCE_DIRECTORY: self.resource_dir,
                BACKTEST_DATA_DIRECTORY_NAME: "market_data_sources_for_testing"
            },
            backtest_start_date=datetime(2023, 12, 17, 00, 00),
            backtest_end_date=datetime(2023, 12, 25, 00, 00),
        )
        self.assertEqual(200, data_source.window_size)
        self.assertEqual(csv_file_path, data_source._create_file_path())
        df = data_source\
            .get_data(
                date=datetime(
                    year=2023, month=12, day=17, hour=0, minute=0
                ),
                config={}
            )
        self.assertEqual(
            ["Datetime", "Open", "High", "Low", "Close", "Volume"], df.columns
        )
