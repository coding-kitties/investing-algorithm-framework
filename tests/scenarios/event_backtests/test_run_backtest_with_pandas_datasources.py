"""
Event backtest scenario: pandas-based data provider.

Verifies that ``app.run_backtest`` works when a ``PandasOHLCVDataProvider``
is attached, using a CSV file from ``tests/resources/test_data/ohlcv/``.

Uses a short (30-day) date range so this test runs well under 30s on CI.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest import TestCase

import polars as pl

from investing_algorithm_framework import (
    create_app,
    BacktestDateRange,
    Algorithm,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
    PandasOHLCVDataProvider,
    convert_polars_to_pandas,
)
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)


class Test(TestCase):

    def test_run(self):
        start_time = time.time()
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        # All test data must come from tests/resources/test_data/.
        csv_file_path = os.path.join(
            resource_directory,
            "test_data",
            "ohlcv",
            "OHLCV_BTC-EUR_BITVAVO_2h_2021-10-25-08-00_2023-12-31-00-00.csv",
        )

        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        algorithm = Algorithm()
        strategy = CrossOverStrategyV1()

        dataframe = pl.read_csv(csv_file_path)
        dataframe = convert_polars_to_pandas(dataframe, add_index=False)
        data_provider = PandasOHLCVDataProvider(
            data_provider_identifier="BTC/EUR-ohlcv-2h",
            dataframe=dataframe,
            market="BITVAVO",
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=200,
        )
        app.add_data_provider(data_provider, priority=1)
        algorithm.add_strategy(strategy)
        backtest = app.run_backtest(
            backtest_date_range=date_range,
            algorithm=algorithm,
            risk_free_rate=0.027,
        )
        elapsed_time = time.time() - start_time
        self.assertLess(
            elapsed_time, 30,
            f"Event backtest took {elapsed_time:.2f}s (expected <30s)"
        )

        metrics = backtest.get_backtest_metrics(date_range)
        run = backtest.get_backtest_run(date_range)
        self.assertEqual(run.initial_unallocated, 400)
        self.assertEqual(run.trading_symbol, "EUR")
        self.assertIsNotNone(metrics.total_growth)
        self.assertAlmostEqual(
            metrics.total_growth, metrics.total_net_gain, delta=0.01
        )
        self.assertAlmostEqual(
            metrics.total_growth_percentage,
            metrics.total_growth / 400.0,
            delta=1e-6,
        )

        snapshots = run.get_portfolio_snapshots()
        self.assertGreater(len(snapshots), 0)
        self.assertEqual(
            snapshots[0].created_at.replace(tzinfo=timezone.utc),
            start_date.replace(tzinfo=timezone.utc),
        )
