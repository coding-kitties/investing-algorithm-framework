import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import DATETIME_FORMAT, DataSource, \
    TimeFrame, BacktestDateRange
from investing_algorithm_framework.infrastructure import \
    CCXTOHLCVDataProvider
from investing_algorithm_framework.services import ConfigurationService


class TestCCXTOHLCVDataProvider(TestCase):
    """
    Test cases for the CCXTOHLCVDataProvider class.
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
        self.configuration_service = ConfigurationService()

    def test_right_columns(self):
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            window_size=10,
            market="bitvavo",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data_provider.config = self.configuration_service.config
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

    def test_has_data(self):
        data_source = DataSource(
            market="BITVAVO",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV"
        )
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            window_size=10,
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
        data_source = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV"
        )
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            window_size=10,
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
        ccxt_ohlcv_market_data_source = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            window_size=200,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data = ccxt_ohlcv_market_data_source.get_data(
            data_source=data_source,
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
        csv_ohlcv_market_data_source = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            window_size=200,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h"
        )
        data = csv_ohlcv_market_data_source.get_data(
            data_source=data_source,
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

        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            data_provider_identifier="test",
            window_size=10,
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
        )
        self.assertEqual("test", data_provider.data_provider_identifier)

    def test_get_market(self):
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            market="test",
            symbol="BTC/EUR",
            window_size=10,
            time_frame="2h",
        )
        self.assertEqual("test", data_provider.market)

    def test_get_symbol(self):
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            symbol="BTC/EUR",
            window_size=10,
            market="bitvavo",
            time_frame="2h",
        )
        self.assertEqual("BTC/EUR", data_provider.symbol)

    def test_prepare_backtest_data(self):
        datasource = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            data_provider_identifier="test",
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )

        data_provider.prepare_backtest_data(
            datasource,
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
        datasource = DataSource(
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
            data_type="OHLCV",
            window_size=200
        )
        data_provider = CCXTOHLCVDataProvider(
            storage_directory=f"{self.resource_dir}/market_data_sources_for_testing/",
            data_provider_identifier="test",
            market="binance",
            symbol="BTC/EUR",
            time_frame="2h",
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )
        data_provider.prepare_backtest_data(
            datasource,
            backtest_date_range.start_date,
            backtest_date_range.end_date,
        )
        index_date = backtest_date_range.start_date

        while index_date <= backtest_date_range.end_date:
            data = data_provider.get_backtest_data(
                datasource,
                index_date
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
