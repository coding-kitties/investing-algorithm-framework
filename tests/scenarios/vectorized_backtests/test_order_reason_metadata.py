"""
Tests for Order.metadata.order_reason in vector backtests.

Verifies that each order created during a vector backtest has the correct
order_reason metadata tag:
  - buy_signal: initial entry buy
  - sell_signal: full exit sell (and cascading close)
  - scale_in: scale-in buy order
  - scale_out: partial close sell order
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, ScalingRule, CSVOHLCVDataProvider

# ═══════════════════════════════════════════════════════════════════════
# Reuses OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv:
#
#  Row 6  (Close=110): BUY
#  Row 8  (Close=115): scale-in #1
#  Row 10 (Close=115): scale-in #2
#  Row 13 (Close=120): scale-out #1
#  Row 14 (Close=120): scale-out #2
#  Row 16 (Close=90):  SELL (full exit)
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


class ScalingStrategy(TradingStrategy):
    """Buy at 110, scale-in at 115, scale-out at 120, sell at 90."""
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    scaling_rules = [
        ScalingRule(
            symbol="BTC", max_entries=3,
            scale_in_percentage=50, scale_out_percentage=50,
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}

    def generate_scale_in_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 115}

    def generate_scale_out_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 120}


class SimpleBuySellStrategy(TradingStrategy):
    """Buy at 110, sell at 90. No scaling."""
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


def _run(strategy_class, algorithm_id):
    resource_dir = str(Path(__file__).parent.parent.parent / 'resources')
    csv_path = str(
        Path(__file__).parent.parent.parent / 'resources' / 'test_data'
        / 'ohlcv' / CSV_FILENAME
    )
    app = create_app(
        name=algorithm_id,
        config={RESOURCE_DIRECTORY: resource_dir},
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
    date_range = BacktestDateRange(
        start_date=START_DATE, end_date=END_DATE
    )
    backtest = app.run_vector_backtest(
        strategy=strategy_class(algorithm_id=algorithm_id),
        backtest_date_range=date_range,
        risk_free_rate=0.027,
    )
    return backtest.get_backtest_run(date_range)


class TestBuySellOrderReason(TestCase):
    """Simple buy/sell without scaling — every order has metadata."""

    @classmethod
    def setUpClass(cls):
        cls.backtest_run = _run(SimpleBuySellStrategy, "BuySellReason")

    def test_buy_order_has_buy_signal_reason(self):
        orders = self.backtest_run.get_orders()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        self.assertGreaterEqual(len(buy_orders), 1)
        for o in buy_orders:
            self.assertEqual(
                o.metadata.get("order_reason"), "buy_signal",
                f"Buy order missing order_reason=buy_signal: {o.to_dict()}"
            )

    def test_sell_order_has_sell_signal_reason(self):
        orders = self.backtest_run.get_orders()
        sell_orders = [o for o in orders if o.order_side == "SELL"]
        self.assertGreaterEqual(len(sell_orders), 1)
        for o in sell_orders:
            self.assertEqual(
                o.metadata.get("order_reason"), "sell_signal",
                f"Sell order missing order_reason=sell_signal: {o.to_dict()}"
            )

    def test_all_orders_have_metadata(self):
        orders = self.backtest_run.get_orders()
        for o in orders:
            self.assertIsInstance(o.metadata, dict)
            self.assertIn("order_reason", o.metadata)


class TestScalingOrderReason(TestCase):
    """
    Scaling strategy: buy, scale-in, scale-out, sell.
    Each order type should have the correct order_reason.
    """

    @classmethod
    def setUpClass(cls):
        cls.backtest_run = _run(ScalingStrategy, "ScalingReason")

    def test_initial_buy_has_buy_signal(self):
        orders = self.backtest_run.get_orders()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        # First buy order is the initial entry
        self.assertGreaterEqual(len(buy_orders), 1)
        self.assertEqual(
            buy_orders[0].metadata.get("order_reason"), "buy_signal"
        )

    def test_scale_in_orders_have_scale_in_reason(self):
        orders = self.backtest_run.get_orders()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        # Should have 3 buys: 1 initial + 2 scale-ins
        self.assertEqual(len(buy_orders), 3)
        # Scale-in orders (index 1 and 2)
        for o in buy_orders[1:]:
            self.assertEqual(
                o.metadata.get("order_reason"), "scale_in",
                f"Scale-in order has wrong reason: {o.metadata}"
            )

    def test_scale_out_orders_have_scale_out_reason(self):
        orders = self.backtest_run.get_orders()
        sell_orders = [o for o in orders if o.order_side == "SELL"]
        scale_out_orders = [
            o for o in sell_orders
            if o.metadata.get("order_reason") == "scale_out"
        ]
        # At least 1 scale-out before the final sell
        self.assertGreaterEqual(
            len(scale_out_orders), 1,
            "Expected at least one scale_out sell order"
        )

    def test_final_sell_has_sell_signal_reason(self):
        orders = self.backtest_run.get_orders()
        sell_orders = [o for o in orders if o.order_side == "SELL"]
        sell_signal_orders = [
            o for o in sell_orders
            if o.metadata.get("order_reason") == "sell_signal"
        ]
        # The full exit sell order(s)
        self.assertGreaterEqual(
            len(sell_signal_orders), 1,
            "Expected at least one sell_signal sell order for full exit"
        )

    def test_all_orders_have_order_reason(self):
        """Every single order has an order_reason in metadata."""
        orders = self.backtest_run.get_orders()
        valid_reasons = {
            "buy_signal", "sell_signal", "scale_in", "scale_out"
        }
        for o in orders:
            reason = o.metadata.get("order_reason")
            self.assertIn(
                reason, valid_reasons,
                f"Order has unexpected order_reason={reason}: "
                f"{o.to_dict()}"
            )

    def test_order_reason_counts(self):
        """
        Expected order distribution for the scaling CSV:
        - 1 buy_signal (initial entry at 110)
        - 2 scale_in (at 115, 115)
        - >=1 scale_out (at 120)
        - >=1 sell_signal (final exit at 90, cascading close)
        """
        orders = self.backtest_run.get_orders()
        reasons = [o.metadata.get("order_reason") for o in orders]
        self.assertEqual(reasons.count("buy_signal"), 1)
        self.assertEqual(reasons.count("scale_in"), 2)
        self.assertGreaterEqual(reasons.count("scale_out"), 1)
        self.assertGreaterEqual(reasons.count("sell_signal"), 1)
