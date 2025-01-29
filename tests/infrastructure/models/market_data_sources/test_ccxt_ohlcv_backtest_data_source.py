import os
from unittest import TestCase
from datetime import datetime, timedelta
from investing_algorithm_framework.infrastructure.models\
    .market_data_sources.ccxt import CCXTOHLCVBacktestMarketDataSource
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    BACKTEST_DATA_DIRECTORY_NAME


class TestCCXTOHLCVBacktestDataSource(TestCase):

    def setUp(self):
        self.resource_dir = os.path.abspath(
            os.path.join(
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
                    os.pardir
                ),
                "resources"
            )
        )
        self.backtest_data_dir = "market_data_sources_for_testing"

    def test_prepare_data(self):
        pass

    def test_get_data(self):
        data_source = CCXTOHLCVBacktestMarketDataSource(
            identifier="bitvavo",
            market="BITVAVO",
            symbol="BTC/EUR",
            time_frame="2h",
            window_size=200,
        )
        config = {
            RESOURCE_DIRECTORY: self.resource_dir,
            BACKTEST_DATA_DIRECTORY_NAME: self.backtest_data_dir
        }
        data_source.prepare_data(
            config=config,
            backtest_start_date=datetime(2021, 1, 1), backtest_end_date=datetime(2025, 1, 1)
        )
        number_of_data_retrievals = 0
        backtest_start_date = datetime(2021, 1, 1)
        backtest_end_date = datetime(2022, 1, 1)
        interval = timedelta(hours=2)  # Define the 2-hour interval
        current_date = backtest_start_date
        delta = backtest_end_date - backtest_start_date
        runs = (delta.total_seconds() / 7200) + 1

        while current_date <= backtest_end_date:
            data = data_source.get_data(date=current_date)

            if data is not None:
                number_of_data_retrievals += 1
                self.assertTrue(abs(200 - len(data)) <= 4)

            current_date += interval  # Increment by 2 hours

        self.assertEqual(runs, number_of_data_retrievals)
