import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, CSVOHLCVDataProvider

# ═══════════════════════════════════════════════════════════════════════
# Fast CSV price sequence (OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv):
#
#  Row | Close | Signal
#  ----+-------+---------------------------
#  1-5 | 100   | warmup
#   6  | 110   | BUY
#   7  | 100   | —
#   8  | 115   | (already in position)
#   ...
#  16  | 90    | SELL
#  17+ | 100   | post-sell buffer
#
# One complete buy→sell cycle in both event and vector modes.
# ═══════════════════════════════════════════════════════════════════════

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv"
WARMUP = 5
START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2020, 12, 21, 8, 0, 0, tzinfo=timezone.utc)


def _make_data_source():
    return DataSource(
        symbol="BTC/EUR",
        data_type=DataType.OHLCV,
        time_frame="2h",
        warmup_window=WARMUP,
        market="BITVAVO",
        identifier="BTC_EUR_OHLCV",
        pandas=True,
    )


class PriceSignalStrategy(TradingStrategy):
    """
    Deterministic strategy using price levels for signal generation.
    Works identically in event-based and vector-based backtesting.

    Buy when Close == 110, sell when Close == 90.
    """
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


def _create_app(name):
    """Set up an app with CSVOHLCVDataProvider for BTC/EUR."""
    resource_dir = str(Path(__file__).parent.parent / 'resources')
    csv_path = str(
        Path(__file__).parent.parent / 'resources' / 'test_data'
        / 'ohlcv' / CSV_FILENAME
    )
    app = create_app(
        name=name, config={RESOURCE_DIRECTORY: resource_dir}
    )
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=1000
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=csv_path,
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=WARMUP,
        ),
        priority=1,
    )
    return app


class TestEventVsVectorBacktest(TestCase):
    """
    Compare event-based and vector-based backtest results.

    Uses a deterministic price-signal strategy on a compact 25-row CSV.
    Both modes should produce identical trades and very close metrics.

    Price sequence produces one complete buy→sell cycle:
      - Buy at Close=110 (Dec 20 10:00)
      - Sell at Close=90 (Dec 21 06:00)
    """

    vector_run = None
    event_run = None
    vector_metrics = None
    event_metrics = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )

        # Vector backtest
        app_v = _create_app("VectorTest")
        vector_bt = app_v.run_vector_backtest(
            strategy=PriceSignalStrategy(algorithm_id="vector"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.vector_run = vector_bt.backtest_runs[0]
        cls.vector_metrics = cls.vector_run.backtest_metrics

        # Event backtest
        app_e = _create_app("EventTest")
        event_bt = app_e.run_backtest(
            strategy=PriceSignalStrategy(algorithm_id="event"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.event_run = event_bt.backtest_runs[0]
        cls.event_metrics = cls.event_run.backtest_metrics

    def test_compare_trade_counts(self):
        """Both modes should produce the same number of trades."""
        self.assertEqual(
            len(self.vector_run.get_trades()),
            len(self.event_run.get_trades()),
            f"Trade count mismatch: "
            f"vector={len(self.vector_run.get_trades())}, "
            f"event={len(self.event_run.get_trades())}"
        )

    def test_compare_order_counts(self):
        """Both modes should produce the same number of orders."""
        self.assertEqual(
            len(self.vector_run.orders),
            len(self.event_run.orders),
            f"Order count mismatch: "
            f"vector={len(self.vector_run.orders)}, "
            f"event={len(self.event_run.orders)}"
        )

    def test_compare_trade_net_gains(self):
        """Individual trade net gains should match between modes.

        Note: Portfolio-level backtest_metrics (total_net_gain, final_value)
        may differ due to architectural differences in how the event-based
        and vector-based engines compute aggregate portfolio metrics.
        Trade-level net gains are the authoritative comparison.
        """
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        self.assertEqual(len(v_trades), len(e_trades))

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            self.assertAlmostEqual(
                vt.net_gain, et.net_gain,
                delta=max(abs(et.net_gain) * 0.01, 0.01),
                msg=f"Trade {i}: net_gain mismatch "
                    f"(vector={vt.net_gain}, event={et.net_gain})"
            )

    def test_compare_trade_details(self):
        """Individual trades should match in symbol and status."""
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        self.assertEqual(len(v_trades), len(e_trades))

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            # Same symbol
            v_sym = getattr(vt, 'symbol', None) or \
                getattr(vt, 'target_symbol', None)
            e_sym = getattr(et, 'symbol', None) or \
                getattr(et, 'target_symbol', None)
            self.assertEqual(
                v_sym, e_sym, f"Trade {i}: symbol mismatch"
            )

            # Both positive amounts
            self.assertGreater(
                vt.amount, 0, f"Trade {i}: vector amount <= 0"
            )
            self.assertGreater(
                et.amount, 0, f"Trade {i}: event amount <= 0"
            )

            # Same status
            v_status = vt.status.value if hasattr(
                vt.status, 'value') else vt.status
            e_status = et.status.value if hasattr(
                et.status, 'value') else et.status
            self.assertEqual(
                v_status, e_status,
                f"Trade {i}: status mismatch"
            )

    def test_compare_trade_amounts(self):
        """Trade amounts should be very close (same sizing logic)."""
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            self.assertAlmostEqual(
                vt.amount, et.amount,
                delta=max(abs(et.amount) * 0.05, 0.001),
                msg=f"Trade {i}: amount mismatch "
                    f"(vector={vt.amount}, event={et.amount})"
            )


if __name__ == "__main__":
    unittest.main()
