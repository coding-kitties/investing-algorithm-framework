"""
Event backtest scenario: window isolation regression test.

Regression test for a bug where event-driven backtests running
multiple (algorithm, window) combinations shared portfolio/order/
trade/position state across windows instead of resetting it, causing
orders and trades from an earlier window to leak into later windows.
See ``BacktestService._reset_event_backtest_state``.

Uses two disjoint, non-adjacent 30-day windows over the offline
BTC/EUR test data so this test runs well under 30s on CI.
"""
import os
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    create_app,
    BacktestDateRange,
    BacktestWindow,
    Study,
    Universe,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
)
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)


def _as_utc(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class Test(TestCase):

    def test_windows_do_not_leak_state(self):
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="WindowIsolationStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )

        # Two disjoint windows (with a gap in between) carved out of
        # the single 30-day range already validated by the other event
        # backtest scenario tests (end 2023-12-02), since the offline
        # test data provider only reliably resolves that range.
        window_a = BacktestDateRange(
            start_date=datetime(2023, 11, 2, tzinfo=timezone.utc),
            end_date=datetime(2023, 11, 15, tzinfo=timezone.utc),
            name="window_a",
        )
        window_b = BacktestDateRange(
            start_date=datetime(2023, 11, 18, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, tzinfo=timezone.utc),
            name="window_b",
        )

        study = Study(
            name="window_isolation_study",
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            initial_capital=400,
            risk_free_rate=0.027,
            backtest_windows=[
                BacktestWindow(train_range=window_a),
                BacktestWindow(train_range=window_b),
            ],
        )

        backtests = app.run_backtest(
            study=study, strategy=CrossOverStrategyV1
        )

        self.assertEqual(1, len(backtests))
        backtest = backtests[0]

        run_a = backtest.get_backtest_run(window_a)
        run_b = backtest.get_backtest_run(window_b)
        self.assertIsNotNone(run_a)
        self.assertIsNotNone(run_b)

        # Each window's run must start from the same freshly
        # capitalized portfolio -- if state leaked between windows,
        # the later run's unallocated cash would reflect the earlier
        # window's leftover balance instead of the configured amount.
        self.assertEqual(400, run_a.initial_unallocated)
        self.assertEqual(400, run_b.initial_unallocated)

        # No order/trade from one window should leak into the other.
        for run, date_range in ((run_a, window_a), (run_b, window_b)):
            for order in run.orders:
                created_at = _as_utc(order.created_at)
                self.assertTrue(
                    date_range.start_date <= created_at
                    <= date_range.end_date,
                    f"Order created at {created_at} leaked outside "
                    f"{date_range.name} ({date_range.start_date} - "
                    f"{date_range.end_date})"
                )
            for trade in run.trades:
                opened_at = _as_utc(trade.opened_at)
                self.assertTrue(
                    date_range.start_date <= opened_at
                    <= date_range.end_date,
                    f"Trade opened at {opened_at} leaked outside "
                    f"{date_range.name} ({date_range.start_date} - "
                    f"{date_range.end_date})"
                )

        # Distinct windows must produce entirely distinct order/trade
        # records -- no duplication/reuse across the reset boundary.
        order_ids_a = {o.id for o in run_a.orders}
        order_ids_b = {o.id for o in run_b.orders}
        self.assertEqual(set(), order_ids_a & order_ids_b)

        trade_ids_a = {t.id for t in run_a.trades}
        trade_ids_b = {t.id for t in run_b.trades}
        self.assertEqual(set(), trade_ids_a & trade_ids_b)
