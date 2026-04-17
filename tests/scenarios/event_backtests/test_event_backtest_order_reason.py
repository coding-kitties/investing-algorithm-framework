"""
End-to-end tests for order_reason metadata in event-based backtests.

Verifies that orders created during an event-based backtest carry
the correct metadata.order_reason after flowing through the full
strategy → context → order_service → DB → BacktestRun pipeline.
"""
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, CSVOHLCVDataProvider, ScalingRule

# Reuse the same CSV as test_event_vs_vector_backtest.py
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


def _create_app(name):
    resource_dir = str(Path(__file__).parent.parent.parent / 'resources')
    csv_path = str(
        Path(__file__).parent.parent.parent / 'resources' / 'test_data'
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


class TestEventBacktestBuySellMetadata(TestCase):
    """
    Event backtest with simple buy/sell strategy.
    Orders go through the full DB pipeline:
      strategy → context → order_service → SQLOrder → DB → BacktestRun
    """
    backtest_run = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )
        app = _create_app("EventBuySellMeta")
        backtest = app.run_backtest(
            strategy=SimpleBuySellStrategy(algorithm_id="event_meta"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.backtest_run = backtest.backtest_runs[0]

    def test_orders_exist(self):
        orders = self.backtest_run.orders
        self.assertGreaterEqual(len(orders), 2, "Expected at least 1 buy + 1 sell")

    def test_buy_order_has_buy_signal_reason(self):
        orders = self.backtest_run.orders
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        self.assertGreaterEqual(len(buy_orders), 1)
        for o in buy_orders:
            self.assertEqual(
                o.metadata.get("order_reason"), "buy_signal",
                f"Event backtest buy order missing order_reason: {o.to_dict()}"
            )

    def test_sell_order_has_sell_signal_reason(self):
        orders = self.backtest_run.orders
        sell_orders = [o for o in orders if o.order_side == "SELL"]
        self.assertGreaterEqual(len(sell_orders), 1)
        for o in sell_orders:
            self.assertEqual(
                o.metadata.get("order_reason"), "sell_signal",
                f"Event backtest sell order missing order_reason: {o.to_dict()}"
            )

    def test_all_orders_have_order_reason(self):
        valid_reasons = {"buy_signal", "sell_signal", "scale_in", "scale_out"}
        for o in self.backtest_run.orders:
            reason = o.metadata.get("order_reason")
            self.assertIn(
                reason, valid_reasons,
                f"Event backtest order has unexpected order_reason={reason}"
            )


class TestEventBacktestScalingMetadata(TestCase):
    """
    Event backtest with scaling strategy.
    Verifies buy_signal, scale_in, scale_out, sell_signal flow through DB.
    """
    backtest_run = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )
        app = _create_app("EventScaleMeta")
        backtest = app.run_backtest(
            strategy=ScalingStrategy(algorithm_id="event_scale"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.backtest_run = backtest.backtest_runs[0]

    def test_orders_exist(self):
        orders = self.backtest_run.orders
        self.assertGreaterEqual(len(orders), 3, "Expected buy + scale-in + sell at minimum")

    def test_initial_buy_has_buy_signal(self):
        orders = self.backtest_run.orders
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        self.assertGreaterEqual(len(buy_orders), 1)
        # First buy should be buy_signal
        self.assertEqual(
            buy_orders[0].metadata.get("order_reason"), "buy_signal"
        )

    def test_all_orders_have_valid_order_reason(self):
        valid_reasons = {
            "buy_signal", "sell_signal", "scale_in", "scale_out"
        }
        for o in self.backtest_run.orders:
            reason = o.metadata.get("order_reason")
            self.assertIn(
                reason, valid_reasons,
                f"Order has unexpected reason={reason}: {o.to_dict()}"
            )


class TestEventVsVectorMetadataConsistency(TestCase):
    """
    Verify that event-based and vector-based backtests produce
    orders with the same order_reason metadata distribution.
    """
    vector_run = None
    event_run = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )

        # Vector
        app_v = _create_app("VectorMetaComp")
        vbt = app_v.run_vector_backtest(
            strategy=SimpleBuySellStrategy(algorithm_id="v_comp"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.vector_run = vbt.backtest_runs[0]

        # Event
        app_e = _create_app("EventMetaComp")
        ebt = app_e.run_backtest(
            strategy=SimpleBuySellStrategy(algorithm_id="e_comp"),
            backtest_date_range=date_range,
            risk_free_rate=0.027,
        )
        cls.event_run = ebt.backtest_runs[0]

    def test_same_order_count(self):
        self.assertEqual(
            len(self.vector_run.orders),
            len(self.event_run.orders),
        )

    def test_same_order_reason_distribution(self):
        """Both modes should produce the same set of order_reasons."""
        v_reasons = sorted(
            [o.metadata.get("order_reason") for o in self.vector_run.orders]
        )
        e_reasons = sorted(
            [o.metadata.get("order_reason") for o in self.event_run.orders]
        )
        self.assertEqual(
            v_reasons, e_reasons,
            f"Vector reasons={v_reasons}, Event reasons={e_reasons}"
        )
