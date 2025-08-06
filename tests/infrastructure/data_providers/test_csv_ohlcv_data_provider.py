import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import OperationalException, \
    DATETIME_FORMAT, DataSource, TimeFrame, BacktestDateRange
from investing_algorithm_framework.infrastructure import \
    CSVOHLCVDataProvider


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
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/market_data_sources/"
                          f"{file_name}",
            window_size=10,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        date = datetime(
            2023, 8, 7, 8, 0, tzinfo=timezone.utc
        )
        df = data_provider.get_data(data_source, start_date=date)
        self.assertEqual(
            ["Datetime", "Open", "High", "Low", "Close", "Volume"],
            df.columns
        )

    def test_throw_exception_when_missing_column_names_columns(self):
        file_name = "OHLCV_BTC-EUR_BINANCE_2h_NO_COLUMNS_2023-" \
                    "08-07-07-59_2023-12-02-00-00.csv"

        with self.assertRaises(OperationalException):
            CSVOHLCVDataProvider(
                storage_path=f"{self.resource_dir}/"
                              "market_data_sources_for_testing/"
                              f"{file_name}",
                window_size=10,
                market="binance",
                symbol="BTC/EUR",
                time_frame="2h"
            )

    def test_has_data(self):
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV"
        )
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/market_data_sources/"
                          f"{file_name}",
            window_size=10,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        self.assertTrue(
            data_provider.has_data(
                data_source,
                start_date=datetime(
                    2023, 8, 8, 7, 59, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=timezone.utc
                )
            )
        )

    def test_has_data_backtest_mode(self):
        start_date = datetime(
            2023, 8, 7, 8, 0, tzinfo=timezone.utc
        )
        end_date = datetime(
            2023, 12, 2, 0, 0, tzinfo=timezone.utc
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            start_date=start_date,
            end_date=end_date
        )
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/market_data_sources/"
                          f"{file_name}",
            window_size=10,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        self.assertFalse(data_provider.has_data(data_source))

        start_date = datetime(
            2023, 9, 7, 7, 59, tzinfo=timezone.utc
        )
        self.assertTrue(
            data_provider.has_data(
                data_source,
                start_date=start_date,
                end_date=end_date
            )
        )


    def test_correct_data_source_start_date_and_end_date(self):
        pass

    def test_get_data_start_date(self):
        """
        Test that the start date is correctly when calling the
        get_data method with a start date. The end date should then
        be calculated based on the window size.
        """
        start_date = datetime(
            2023, 8, 7, 8, 0, tzinfo=timezone.utc
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            window_size=200,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data = csv_ohlcv_market_data_source.get_data(
            start_date=start_date
        )
        self.assertAlmostEqual(200, len(data), delta=1)
        first_date = data["Datetime"][0]
        last_date = data["Datetime"][-1]
        self.assertEqual(
            start_date.strftime(DATETIME_FORMAT),
            first_date.strftime(DATETIME_FORMAT)
        )
        end_date = start_date + timedelta(minutes=TimeFrame.TWO_HOUR.amount_of_minutes * (len(data) - 1))
        self.assertEqual(
            last_date.strftime(DATETIME_FORMAT),
            end_date.strftime(DATETIME_FORMAT),
        )

    def test_get_data_end_date(self):
        """
        Test that the end date is correctly when calling the
        get_data method with an end date. The start date should then
        be calculated based on the window size.
        """
        end_date = datetime(
            2023, 8, 31, 8, 0, tzinfo=timezone.utc
        )
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        csv_ohlcv_market_data_source = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                      "market_data_sources/"
                      f"{file_name}",
            window_size=200,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data = csv_ohlcv_market_data_source.get_data(
            end_date=end_date
        )
        self.assertAlmostEqual(200, len(data), delta=1)
        first_date = data["Datetime"][0]
        last_date = data["Datetime"][-1]
        self.assertEqual(
            end_date.strftime(DATETIME_FORMAT),
            last_date.strftime(DATETIME_FORMAT)
        )
        start_date = end_date - timedelta(
            minutes=TimeFrame.TWO_HOUR.amount_of_minutes * (len(data) - 1))
        self.assertEqual(
            first_date.strftime(DATETIME_FORMAT),
            start_date.strftime(DATETIME_FORMAT),
        )

    def test_get_identifier(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            data_provider_identifier="test",
            window_size=10,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
        )
        self.assertEqual("test", data_provider.data_provider_identifier)

    def test_get_market(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            market="test",
            symbol="BTC/EUR",
            window_size=10,
            time_frame="2h",
        )
        self.assertEqual("TEST", data_provider.market)

    def test_get_symbol(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            symbol="BTC/EUR",
            window_size=10,
            market="bitvavo",
            time_frame="2h",
        )
        self.assertEqual("BTC/EUR", data_provider.symbol)

    def test_prepare_backtest_data(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        datasource = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                          "market_data_sources/"
                          f"{file_name}",
            data_provider_identifier="test",
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            window_size=200
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )
        data_provider.prepare_backtest_data(
            backtest_date_range.start_date,
            backtest_date_range.end_date,
        )

        required_start_date = backtest_date_range.start_date - \
            timedelta(
                minutes=TimeFrame.from_value(datasource.time_frame)
                .amount_of_minutes * datasource.window_size
            )

        # Check if for an entries in the window cache a 200 window size
        # data entry is present
        for key, value in data_provider.window_cache.items():
            self.assertAlmostEqual(200, len(value), delta=1)

            # Check that the last date in the window cache is equal or before
            # the end date of the backtest date range
            last_date = value["Datetime"][-1]
            self.assertLessEqual(
                last_date,
                backtest_date_range.end_date
            )

            # Check that the first date in the window cache is equal or after
            # the required start date
            first_date = value["Datetime"][0]
            self.assertGreaterEqual(
                first_date,
                required_start_date
            )

    def test_get_backtest_data(self):
        file_name = "OHLCV_BTC-EUR_BINANCE" \
                    "_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
        datasource = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        data_provider = CSVOHLCVDataProvider(
            storage_path=f"{self.resource_dir}/"
                      "market_data_sources/"
                      f"{file_name}",
            data_provider_identifier="test",
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            window_size=200
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )
        data_provider.prepare_backtest_data(
            backtest_date_range.start_date,
            backtest_date_range.end_date,
        )

        index_date = backtest_date_range.start_date

        while index_date <= backtest_date_range.end_date:
            data = data_provider.get_backtest_data(
                backtest_index_date=index_date
            )
            self.assertAlmostEqual(
                200, len(data), delta=1
            )
            last_row = data[-1]
            # Convert both values to strings
            self.assertEqual(
                last_row["Datetime"][0].strftime(DATETIME_FORMAT),
                index_date.strftime(DATETIME_FORMAT)
            )
            index_date += timedelta(
                minutes=TimeFrame.from_value(datasource.time_frame)
                .amount_of_minutes
            )
