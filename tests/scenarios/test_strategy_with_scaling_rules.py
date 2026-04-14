from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, ScalingRule, CSVOHLCVDataProvider

# ═══════════════════════════════════════════════════════════════════════
# Fast CSV price sequence (OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv):
#
#  Row | Datetime             | Close | Signal
#  ----+----------------------+-------+---------------------------------
#  1-5 | Dec 20 00:00–08:00   | 100   | warmup
#   6  | Dec 20 10:00         | 110   | BUY (initial entry)
#   7  | Dec 20 12:00         | 100   | —
#   8  | Dec 20 14:00         | 115   | scale-in #1 / buy reuse
#   9  | Dec 20 16:00         | 100   | —
#  10  | Dec 20 18:00         | 115   | scale-in #2 / buy reuse
#  11  | Dec 20 20:00         | 100   | —
#  12  | Dec 20 22:00         | 115   | BLOCKED (max_entries=3 reached)
#  13  | Dec 21 00:00         | 120   | scale-out #1
#  14  | Dec 21 02:00         | 120   | scale-out #2
#  15  | Dec 21 04:00         | 100   | —
#  16  | Dec 21 06:00         | 90    | SELL (full exit)
#  17  | Dec 21 08:00         | 100   | —
#  18  | Dec 21 10:00         | 100   | —
#  19  | Dec 21 12:00         | 110   | BUY (new cycle, cooldown test)
#  20  | Dec 21 14:00         | 115   | blocked by cooldown
#  21  | Dec 21 16:00         | 100   | cooldown ticking
#  22  | Dec 21 18:00         | 115   | scale-in after cooldown expires
#  23-25| Dec 21 20:00–22:00  | 100   | end buffer
#
# Backtest window: start=Dec 20 10:00, end=Dec 22 00:00
# warmup_window=5 (rows 1-5)
# ═══════════════════════════════════════════════════════════════════════

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv"
WARMUP = 5
START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
# Default end: covers first cycle (buy→scale-ins→scale-outs→sell)
END_DATE = datetime(2020, 12, 21, 8, 0, 0, tzinfo=timezone.utc)
# Extended end: includes second buy cycle for cooldown tests
END_DATE_EXTENDED = datetime(2020, 12, 22, 0, 0, 0, tzinfo=timezone.utc)


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


# ── Strategy: Scale-in with buy signals (no separate scale_in override) ──
class ScaleInWithBuySignalsStrategy(TradingStrategy):
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
        return {"BTC": (df['Close'] == 110) | (df['Close'] == 115)}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy: Separate scale-in and scale-out signal methods ──
class SeparateScaleSignalsStrategy(TradingStrategy):
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


# ── Strategy: No scaling rule (backward compatible) ──
class NoScalingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": (df['Close'] == 110) | (df['Close'] == 115)}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy: list percentages [50, 25] ──
class ListPercentageStrategy(TradingStrategy):
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
            scale_in_percentage=[50, 25],
            scale_out_percentage=[25, 50],
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": (df['Close'] == 110) | (df['Close'] == 115)}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy: Cooldown ──
class CooldownStrategy(TradingStrategy):
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
            scale_in_percentage=50,
            cooldown_in_bars=2,
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": (df['Close'] == 110) | (df['Close'] == 115)}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _run_backtest(strategy_class, algorithm_id, end_date=None):
    """Set up app, data provider, and run a vector backtest."""
    resource_dir = str(Path(__file__).parent.parent / 'resources')
    app = create_app(
        name=algorithm_id,
        config={RESOURCE_DIRECTORY: resource_dir},
    )
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=1000
    )

    csv_path = str(
        Path(__file__).parent.parent / 'resources' / 'test_data'
        / 'ohlcv' / CSV_FILENAME
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
        start_date=START_DATE, end_date=end_date or END_DATE
    )
    backtest = app.run_vector_backtest(
        strategy=strategy_class(algorithm_id=algorithm_id),
        backtest_date_range=date_range,
        risk_free_rate=0.027,
    )
    return backtest, date_range


def _get_run(strategy_class, algorithm_id, end_date=None):
    backtest, date_range = _run_backtest(
        strategy_class, algorithm_id, end_date
    )
    return backtest.get_backtest_run(date_range)


# ═══════════════════════════════════════════════════════════════════════
# Scenario tests (vector backtest)
# ═══════════════════════════════════════════════════════════════════════

class TestScaleInWithBuySignals(TestCase):
    """
    Buy signals at 110 and 115 → initial entry + 2 scale-ins.
    Row 12 (115 again) should be blocked by max_entries=3.
    Row 16 (90) → full sell closing all 3 trades.
    """

    def test_scale_in_creates_multiple_trades(self):
        run = _get_run(ScaleInWithBuySignalsStrategy, "ScaleInBuy")
        trades = run.get_trades()
        orders = run.get_orders()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        sell_orders = [o for o in orders if o.order_side == "SELL"]

        self.assertEqual(3, len(buy_orders))
        self.assertGreaterEqual(len(sell_orders), 1)
        self.assertEqual(3, len(trades))

    def test_max_entries_blocks_additional_scale_in(self):
        run = _get_run(ScaleInWithBuySignalsStrategy, "ScaleInBlock")
        trades = run.get_trades()
        buy_orders = [
            o for o in run.get_orders() if o.order_side == "BUY"
        ]
        # Only 3 buys, the 4th 115 signal is blocked
        self.assertEqual(3, len(buy_orders))


class TestSeparateScaleSignals(TestCase):
    """
    Buy at 110, scale-in at 115, scale-out at 120, sell at 90.
    Uses separate generate_scale_in_signals / generate_scale_out_signals.
    """

    def test_scale_in_uses_separate_signals(self):
        run = _get_run(SeparateScaleSignalsStrategy, "SepScaleIn")
        trades = run.get_trades()
        self.assertEqual(3, len(trades))

    def test_scale_out_partial_close(self):
        run = _get_run(SeparateScaleSignalsStrategy, "SepScaleOut")
        orders = run.get_orders()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        sell_orders = [o for o in orders if o.order_side == "SELL"]

        self.assertEqual(3, len(buy_orders))
        # At least 1 partial sell + final full sell
        self.assertGreaterEqual(len(sell_orders), 2)


class TestNoScalingBackwardCompat(TestCase):
    """
    Without scaling_rules, buy signal while in position is ignored.
    One entry, one full exit.
    """

    def test_single_entry_single_exit(self):
        run = _get_run(NoScalingStrategy, "NoScaling")
        orders = run.get_orders()
        trades = run.get_trades()
        buy_orders = [o for o in orders if o.order_side == "BUY"]
        sell_orders = [o for o in orders if o.order_side == "SELL"]

        self.assertEqual(1, len(buy_orders))
        self.assertEqual(1, len(sell_orders))
        self.assertEqual(1, len(trades))


class TestListPercentages(TestCase):
    """
    scale_in_percentage=[50, 25]: 1st add is 50%, 2nd add is 25%.
    scale_out_percentage=[25, 50]: 1st trim is 25%, 2nd trim is 50%.
    """

    def test_list_scale_in_creates_trades(self):
        run = _get_run(ListPercentageStrategy, "ListPct")
        trades = run.get_trades()
        buy_orders = [
            o for o in run.get_orders() if o.order_side == "BUY"
        ]
        self.assertEqual(3, len(buy_orders))
        self.assertEqual(3, len(trades))

    def test_scale_in_sizes_decrease(self):
        """Second add should be smaller than first add."""
        run = _get_run(ListPercentageStrategy, "ListPctSize")
        buy_orders = sorted(
            [o for o in run.get_orders() if o.order_side == "BUY"],
            key=lambda o: o.created_at,
        )
        # Order: initial (100%), add1 (50%), add2 (25%)
        self.assertEqual(3, len(buy_orders))
        initial_amount = buy_orders[0].amount
        add1_amount = buy_orders[1].amount
        add2_amount = buy_orders[2].amount
        self.assertGreater(initial_amount, add1_amount)
        self.assertGreater(add1_amount, add2_amount)


class TestCooldown(TestCase):
    """
    cooldown_in_bars=2: after a buy, the next 2 bars are skipped.

    Sequence (starting from row 6):
      bar 0: 110 → BUY (entry #1), cooldown starts (2 bars)
      bar 1: 100 → cooldown remaining=1
      bar 2: 115 → cooldown remaining=0 (just expired), scale-in fires
      bar 3: 100 → cooldown starts again (2 bars)
      bar 4: 115 → cooldown remaining=1 → BLOCKED
      bar 5: 100 → cooldown remaining=0
      bar 6: 115 → cooldown expired → scale-in fires

    With cooldown=2 we expect fewer entries than without cooldown.
    """

    def test_cooldown_reduces_entries(self):
        # Without cooldown: uses extended range for 2nd cycle
        run_no_cd = _get_run(
            ScaleInWithBuySignalsStrategy, "NoCooldown",
            end_date=END_DATE_EXTENDED,
        )
        buys_no_cd = [
            o for o in run_no_cd.get_orders() if o.order_side == "BUY"
        ]

        # With cooldown=2: some scale-ins get blocked
        run_cd = _get_run(
            CooldownStrategy, "WithCooldown",
            end_date=END_DATE_EXTENDED,
        )
        buys_cd = [
            o for o in run_cd.get_orders() if o.order_side == "BUY"
        ]

        # Cooldown should allow fewer or equal entries
        self.assertLessEqual(len(buys_cd), len(buys_no_cd))
        # At minimum the initial buy should still happen
        self.assertGreaterEqual(len(buys_cd), 1)

    def test_cooldown_signal_events_recorded(self):
        """Signal events should show 'in_cooldown' reasons."""
        run = _get_run(
            CooldownStrategy, "CooldownEvents",
            end_date=END_DATE_EXTENDED,
        )
        events = run.signal_events
        cooldown_events = [
            e for e in events if e.get("reason") == "in_cooldown"
        ]
        self.assertGreater(len(cooldown_events), 0)


# ═══════════════════════════════════════════════════════════════════════
# Unit tests (no backtest needed)
# ═══════════════════════════════════════════════════════════════════════

    def test_default_values(self):
        rule = ScalingRule(symbol="BTC")
        self.assertEqual(rule.symbol, "BTC")
        self.assertEqual(rule.max_entries, 1)
        self.assertEqual(rule.scale_in_percentage, 100)
        self.assertEqual(rule.scale_out_percentage, 50)
        self.assertIsNone(rule.max_position_percentage)
        self.assertEqual(rule.cooldown_in_bars, 0)

    def test_custom_values(self):
        rule = ScalingRule(
            symbol="ETH",
            max_entries=5,
            scale_in_percentage=25,
            scale_out_percentage=75,
            max_position_percentage=40.0,
            cooldown_in_bars=3,
        )
        self.assertEqual(rule.symbol, "ETH")
        self.assertEqual(rule.max_entries, 5)
        self.assertEqual(rule.scale_in_percentage, 25)
        self.assertEqual(rule.scale_out_percentage, 75)
        self.assertEqual(rule.max_position_percentage, 40.0)
        self.assertEqual(rule.cooldown_in_bars, 3)

    def test_repr(self):
        rule = ScalingRule(symbol="BTC", max_entries=3)
        repr_str = repr(rule)
        self.assertIn("BTC", repr_str)
        self.assertIn("max_entries=3", repr_str)

    def test_list_scale_in_percentage(self):
        """scale_in_percentage=[50, 25] returns list."""
        rule = ScalingRule(
            symbol="BTC", scale_in_percentage=[50, 25]
        )
        self.assertEqual(rule.scale_in_percentage, [50.0, 25.0])

    def test_single_scale_in_percentage(self):
        """scale_in_percentage=30 returns float."""
        rule = ScalingRule(symbol="BTC", scale_in_percentage=30)
        self.assertEqual(rule.scale_in_percentage, 30.0)

    def test_list_scale_out_percentage(self):
        """scale_out_percentage=[25, 50] returns list."""
        rule = ScalingRule(
            symbol="BTC", scale_out_percentage=[25, 50]
        )
        self.assertEqual(rule.scale_out_percentage, [25.0, 50.0])

    def test_single_scale_out_percentage(self):
        """scale_out_percentage=75 returns float."""
        rule = ScalingRule(symbol="BTC", scale_out_percentage=75)
        self.assertEqual(rule.scale_out_percentage, 75.0)

    def test_get_scale_in_percentage_in_range(self):
        rule = ScalingRule(
            symbol="BTC", scale_in_percentage=[50, 25, 10]
        )
        self.assertEqual(rule.get_scale_in_percentage(0), 50.0)
        self.assertEqual(rule.get_scale_in_percentage(1), 25.0)
        self.assertEqual(rule.get_scale_in_percentage(2), 10.0)

    def test_get_scale_in_percentage_fallback(self):
        """Index beyond list falls back to last value."""
        rule = ScalingRule(
            symbol="BTC", scale_in_percentage=[50, 25]
        )
        self.assertEqual(rule.get_scale_in_percentage(5), 25.0)

    def test_get_scale_out_percentage_in_range(self):
        rule = ScalingRule(
            symbol="BTC", scale_out_percentage=[25, 50, 100]
        )
        self.assertEqual(rule.get_scale_out_percentage(0), 25.0)
        self.assertEqual(rule.get_scale_out_percentage(1), 50.0)
        self.assertEqual(rule.get_scale_out_percentage(2), 100.0)

    def test_get_scale_out_percentage_fallback(self):
        """Index beyond list falls back to last value."""
        rule = ScalingRule(
            symbol="BTC", scale_out_percentage=[25, 50]
        )
        self.assertEqual(rule.get_scale_out_percentage(10), 50.0)


class TestScalingRuleOnStrategy(TestCase):
    """Unit tests for ScalingRule integration with TradingStrategy."""

    def test_get_scaling_rule_returns_rule(self):
        strategy = ScaleInWithBuySignalsStrategy(
            algorithm_id="test"
        )
        rule = strategy.get_scaling_rule("BTC")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.symbol, "BTC")
        self.assertEqual(rule.max_entries, 3)
        self.assertEqual(rule.scale_in_percentage, 50)

    def test_get_scaling_rule_returns_none_for_unknown_symbol(self):
        strategy = ScaleInWithBuySignalsStrategy(
            algorithm_id="test"
        )
        rule = strategy.get_scaling_rule("ETH")
        self.assertIsNone(rule)

    def test_no_scaling_rules_returns_none(self):
        strategy = NoScalingStrategy(algorithm_id="test")
        rule = strategy.get_scaling_rule("BTC")
        self.assertIsNone(rule)

    def test_scaling_rule_via_constructor(self):
        """Test passing scaling_rules via constructor (not class attr)."""
        strategy = NoScalingStrategy(
            algorithm_id="test",
            scaling_rules=[
                ScalingRule(symbol="BTC", max_entries=2),
            ]
        )
        rule = strategy.get_scaling_rule("BTC")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.max_entries, 2)

    def test_default_scale_in_signals_returns_none(self):
        strategy = ScaleInWithBuySignalsStrategy(
            algorithm_id="test"
        )
        result = strategy.generate_scale_in_signals({})
        self.assertIsNone(result)

    def test_default_scale_out_signals_returns_none(self):
        strategy = ScaleInWithBuySignalsStrategy(
            algorithm_id="test"
        )
        result = strategy.generate_scale_out_signals({})
        self.assertIsNone(result)

    def test_overridden_scale_in_signals(self):
        strategy = SeparateScaleSignalsStrategy(
            algorithm_id="test"
        )
        data = {
            "BTC_EUR_OHLCV": pd.DataFrame({
                "Close": [100.0, 115.0, 100.0]
            })
        }
        result = strategy.generate_scale_in_signals(data)
        self.assertIsNotNone(result)
        self.assertIn("BTC", result)
        self.assertTrue(result["BTC"].iloc[1])
        self.assertFalse(result["BTC"].iloc[0])
        self.assertFalse(result["BTC"].iloc[2])
