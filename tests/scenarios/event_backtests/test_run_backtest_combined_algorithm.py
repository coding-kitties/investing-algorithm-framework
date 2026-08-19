"""
Event backtest scenario: combined multi-strategy ``algorithm=`` parameter.

Verifies that ``app.run_backtest(algorithm=...)`` with an Algorithm that
has MORE THAN ONE strategy registered runs all of them TOGETHER, sharing
one portfolio, in ONE combined ``Backtest`` (as opposed to
``strategies=[...]``, which runs each strategy as its own independent
backtest for comparison).

Also verifies that the vector engine explicitly rejects a combined
multi-strategy algorithm (not supported yet) instead of silently doing
the wrong thing.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    create_app,
    Algorithm,
    BacktestDateRange,
    OperationalException,
    PositionSize,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
    Schedule,
    SnapshotInterval,
    TimeUnit,
    TradingStrategy,
    Study,
    Universe,
    BacktestWindow,
    BacktestEngine,
)
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)


class _VectorOnlyStrategy(TradingStrategy):
    """Minimal strategy that only implements the vector-engine hook,
    used to force ``run_backtest``'s engine auto-detection to VECTOR."""
    schedule = Schedule.every(2, TimeUnit.HOUR)

    def generate_signal_series(self, data):
        return iter(())


class TestRunBacktestCombinedAlgorithm(TestCase):

    def test_event_engine_runs_strategies_together(self):
        start_time = time.time()
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="CombinedAlgorithm", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )

        btc_strategy = CrossOverStrategyV1(
            algorithm_id="combined_algo", symbols=["BTC"]
        )
        btc_strategy.strategy_id = "crossover_btc"
        dot_strategy = CrossOverStrategyV1(
            algorithm_id="combined_algo", symbols=["DOT"]
        )
        dot_strategy.strategy_id = "crossover_dot"
        dot_strategy.position_sizes = [
            PositionSize(symbol="DOT", percentage_of_portfolio=20.0)
        ]
        dot_strategy.position_sizes_lookup = {}

        algorithm = Algorithm(algorithm_id="combined_algo")
        algorithm.add_strategy(btc_strategy)
        algorithm.add_strategy(dot_strategy)

        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=date_range)],
            engines=[BacktestEngine.EVENT_DRIVEN],
        )
        backtests = app.run_backtest(
            algorithm=algorithm,
            study=study,
            snapshot_interval=SnapshotInterval.DAILY,
        )
        elapsed_time = time.time() - start_time
        self.assertLess(
            elapsed_time, 30,
            f"Event backtest took {elapsed_time:.2f}s (expected <30s)"
        )

        # One combined Backtest containing BOTH strategies, not two
        # independent ones.
        self.assertEqual(
            {"crossover_btc", "crossover_dot"}, set(backtests[0].strategy_ids)
        )

        backtest_run = backtests[0].get_backtest_run(date_range)
        # A single shared portfolio, capitalised once.
        self.assertEqual(backtest_run.initial_unallocated, 400)
        self.assertEqual(
            backtest_run.portfolio_snapshots[0].trading_symbol, "EUR"
        )

    def test_orders_and_trades_are_attributed_to_the_correct_strategy(self):
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="CombinedAlgorithmAttribution", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )

        btc_strategy = CrossOverStrategyV1(
            algorithm_id="combined_algo", symbols=["BTC"]
        )
        btc_strategy.strategy_id = "crossover_btc"
        dot_strategy = CrossOverStrategyV1(
            algorithm_id="combined_algo", symbols=["DOT"]
        )
        dot_strategy.strategy_id = "crossover_dot"
        dot_strategy.position_sizes = [
            PositionSize(symbol="DOT", percentage_of_portfolio=20.0)
        ]
        dot_strategy.position_sizes_lookup = {}

        algorithm = Algorithm(algorithm_id="combined_algo")
        algorithm.add_strategy(btc_strategy)
        algorithm.add_strategy(dot_strategy)

        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=date_range)],
            engines=[BacktestEngine.EVENT_DRIVEN],
        )
        backtests = app.run_backtest(
            algorithm=algorithm,
            study=study,
            snapshot_interval=SnapshotInterval.DAILY,
        )
        backtest_run = backtests[0].get_backtest_run(date_range)

        self.assertGreater(len(backtest_run.orders), 0)
        self.assertGreater(len(backtest_run.trades), 0)

        for order in backtest_run.orders:
            expected_strategy_id = (
                "crossover_btc" if order.target_symbol == "BTC"
                else "crossover_dot"
            )
            self.assertEqual(expected_strategy_id, order.strategy_id)

        for trade in backtest_run.trades:
            expected_strategy_id = (
                "crossover_btc" if trade.target_symbol == "BTC"
                else "crossover_dot"
            )
            self.assertEqual(expected_strategy_id, trade.strategy_id)

    def test_vector_engine_rejects_combined_multi_strategy(self):
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="CombinedVectorAlgorithm", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )

        algorithm = Algorithm(algorithm_id="combined_vector_algo")
        algorithm.add_strategy(_VectorOnlyStrategy())
        second = _VectorOnlyStrategy()
        second.strategy_id = "vector_only_2"
        algorithm.add_strategy(second)

        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=date_range)],
            engines=[BacktestEngine.VECTOR],
        )
        with self.assertRaises(OperationalException):
            app.run_backtest(
                algorithm=algorithm,
                study=study,
                snapshot_interval=SnapshotInterval.DAILY,
            )
