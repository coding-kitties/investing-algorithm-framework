"""
This example demonstrates the use of the QuantOS testing framework
with a sample RSI and EMA strategy.

The goal of this example is to illustrate how you can create different
scenarios for your trading strategy to test its behavior.

Scenarios define portfolio state and market conditions to test how your
strategy reacts to them. Previews do not advance simulation time or submit
orders; they let you inspect sizing, risk rules and cooldowns.

The goal of this framework is to help developers write robust and reliable
tests for their trading strategies.
"""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import pandas as pd
from pyindicators import ema, rsi

from investing_algorithm_framework import (
    ConfluenceScoreConfig,
    ConfluenceScoringStrategy,
    CooldownRule,
    DataSource,
    IndicatorConfig,
    IndicatorRule,
    PositionSize,
    ScenarioSetupError,
    Schedule,
    SignalSide,
    StopLossRule,
    StrategyScenario,
    TakeProfitRule,
    TimeUnit,
)


START = datetime(2025, 1, 15, tzinfo=timezone.utc)
BAR = timedelta(hours=2)


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    data = rsi(data, source_column="Close", period=14, result_column="rsi")
    data = ema(data, source_column="Close", period=20, result_column="ema_20")
    data = ema(data, source_column="Close", period=50, result_column="ema_50")
    data["ema_spread"] = data["ema_20"] - data["ema_50"]
    return data


class RSIEMAConfluenceStrategy(ConfluenceScoringStrategy):
    """Buy an oversold uptrend; exit on overbought RSI or a downtrend."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            identifier="btc_2h",
            symbol="BTC/EUR",
            market="BITVAVO",
            data_type="OHLCV",
            time_frame="2h",
            warmup_window=50,
            pandas=True,
        ),
    ]
    indicator_configs = [
        IndicatorConfig(
            id="momentum",
            calculate=calculate_indicators,
            data_source="btc_2h", timeframe="2h",
            output_columns=["rsi", "ema_spread"],
            minimum_history=50,
            execution="precompute",
        ),
    ]
    confluence_cards = [
        ConfluenceScoreConfig(
            id="long_entry", side=SignalSide.OPEN_LONG, symbols=["BTC"],
            rules={
                "oversold": IndicatorRule(
                    indicator_id="momentum",
                    output_column="rsi",
                    threshold=30,
                    comparison="le",
                    group_weights={"primary": 1},
                ),
                "uptrend": IndicatorRule(
                    indicator_id="momentum",
                    output_column="ema_spread",
                    threshold=0,
                    comparison="gt",
                    group_weights={"primary": 1},
                ),
            },
            group_thresholds={"primary": 2},
        ),
        ConfluenceScoreConfig(
            id="long_exit", side=SignalSide.CLOSE_LONG, symbols=["BTC"],
            rules={
                "overbought": IndicatorRule(
                    indicator_id="momentum",
                    output_column="rsi",
                    threshold=70,
                    comparison="ge",
                    group_weights={"primary": 1},
                ),
                "downtrend": IndicatorRule(
                    indicator_id="momentum",
                    output_column="ema_spread",
                    threshold=0,
                    comparison="lt",
                    group_weights={"primary": 1},
                ),
            },
            group_thresholds={"primary": 1},
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100,
            trailing=True,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=20, sell_percentage=100,
        ),
    ]
    cooldowns = [
        CooldownRule(symbol="BTC", trigger="buy", blocks="buy", bars=3),
    ]


def genereate_ohlcv_data(close):
    """Create completed candles ending one full bar before scenario time."""
    frame = pd.DataFrame(
        {"Close": close},
        index=pd.date_range(
            end=START - BAR, periods=len(close), freq="2h", tz="UTC",
        ),
    )
    frame["Open"] = frame["Close"]
    frame["High"] = frame["Close"] + 1
    frame["Low"] = frame["Close"] - 1
    frame["Volume"] = 1_000.
    return {"btc_2h": frame}


class TestConfluenceStrategyScenario(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.create_connection"):
            patcher = patch(
                target,
                side_effect=AssertionError("This example must stay offline"),
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_initialization(self):
        """
        Test if the strategy on first load initializes correctly.
        The following aspects are checked for correct initialization:

        - Position sizes
        - Stop loss rules
        - Take profit rules
        - Cooldowns
        """
        strategy = RSIEMAConfluenceStrategy()

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            self.assertAlmostEqual(
                scenario.get_position_size("BTC", price=100), 250,
            )
            preview = scenario.preview_order("BTC", price=100)
            self.assertTrue(preview.approved)
            self.assertAlmostEqual(preview.orders[0].quote_amount, 250)
            self.assertAlmostEqual(preview.orders[0].amount, 2.5)

            stop_rule = scenario.get_stop_loss_rule("BTC")
            self.assertEqual(stop_rule.percentage_threshold, 5)
            self.assertTrue(stop_rule.trailing)
            profit_rule = scenario.get_take_profit_rule("BTC")
            self.assertEqual(profit_rule.percentage_threshold, 20)
            self.assertFalse(profit_rule.trailing)
            stop = scenario.preview_stop_loss("BTC", price=100, amount=2.5)
            profit = scenario.preview_take_profit(
                "BTC", price=100, amount=2.5,
            )
            self.assertAlmostEqual(stop.stop_loss_price, 95)
            self.assertAlmostEqual(profit.take_profit_price, 120)
            self.assertAlmostEqual(stop.sell_amount, 2.5)
            self.assertAlmostEqual(profit.sell_amount, 2.5)

            self.assertEqual(scenario.get_cooldown_rules("BTC")[0].bars, 3)
            cooldown = scenario.preview_cooldown("BTC")
            self.assertFalse(cooldown.blocked)
            self.assertEqual(cooldown.remaining_bars, 0)
            self.assertEqual(scenario.context.get_open_orders(), [])
            self.assertEqual(scenario.context.get_trades(), [])
            scenario.check_consistency()

    def test_cooldown_preview_does_not_consume_history(self):
        strategy = RSIEMAConfluenceStrategy()

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:

            scenario.record_cooldown(
                "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
            )

            for _ in range(2):
                cooldown = scenario.preview_cooldown("BTC")

                # Check that the cooldown is active
                self.assertTrue(cooldown.blocked)

                # Check that the remaining bars are correctly reported
                self.assertEqual(cooldown.remaining_bars, 2)

                # New orders for btc should be blocked due to the cooldown
                self.assertFalse(scenario.preview_order(
                    "BTC", price=100,
                ).approved)

            # Previews do not consume bars. This buy-blocking rule still
            # permits sell-side signals.
            self.assertFalse(scenario.preview_cooldown(
                "BTC", side=SignalSide.CLOSE_LONG,
            ).blocked)
            self.assertEqual(scenario.now, START)

            # Check that all internal states are consistent and valid.
            scenario.check_consistency()

    def test_sizing_override_is_used_by_the_scenario(self):

        class DynamicStrategy(RSIEMAConfluenceStrategy):

            def get_position_size(self, symbol):
                return PositionSize(
                    symbol=symbol,
                    fixed_amount=self.context.get_unallocated() * 0.1,
                )

        strategy = DynamicStrategy()

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            self.assertAlmostEqual(
                scenario.get_position_size("BTC", price=100), 100,
            )
            preview = scenario.preview_order("BTC", price=100)
            self.assertAlmostEqual(preview.orders[0].quote_amount, 100)
            self.assertAlmostEqual(preview.orders[0].amount, 1)

            scenario.place_order("ETH", side="BUY", amount=4, price=100)

            self.assertAlmostEqual(scenario.context.get_unallocated(), 600)
            self.assertAlmostEqual(
                scenario.get_position_size(
                    "BTC", price=100, prices={"ETH": 100},
                ),
                60,
            )
            preview = scenario.preview_order(
                "BTC", price=100, prices={"ETH": 100},
            )
            self.assertTrue(preview.approved)
            self.assertAlmostEqual(preview.orders[0].quote_amount, 60)
            self.assertAlmostEqual(preview.orders[0].amount, 0.6)
            self.assertAlmostEqual(scenario.context.get_unallocated(), 600)
            self.assertEqual(len(scenario.context.get_open_orders()), 1)
            scenario.check_consistency()

    def test_preview_applies_cash_limits_and_explains_blocked_orders(self):
        strategy = RSIEMAConfluenceStrategy(position_sizes=[
            PositionSize(symbol="BTC", fixed_amount=250),
        ])

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            scenario.place_order("ETH", side="BUY", amount=9, price=100)
            self.assertAlmostEqual(
                scenario.get_position_size(
                    "BTC", price=100, prices={"ETH": 100},
                ),
                250,
            )
            preview = scenario.preview_order(
                "BTC", price=100, prices={"ETH": 100},
            )
            self.assertAlmostEqual(preview.orders[0].quote_amount, 100)
            self.assertAlmostEqual(preview.orders[0].amount, 1)

            scenario.place_order("BTC", side="BUY", amount=0.5, price=100)
            blocked = scenario.preview_order(
                "BTC", price=100, prices={"ETH": 100},
            )
            self.assertFalse(blocked.approved)
            self.assertIn(
                "resolve_conflicts.blocked_open_order", dict(blocked.traces),
            )
            self.assertEqual(scenario.context.get_unallocated(), 50)
            scenario.check_consistency()

    def test_flat_portfolio_generates_an_entry_intent(self):
        strategy = RSIEMAConfluenceStrategy()
        history = genereate_ohlcv_data(
            [100 + i for i in range(100)]
            + [199 - i * 0.5 for i in range(20)],
        )

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:

            self.assertEqual(scenario.context.get_unallocated(), 1_000)
            self.assertEqual(scenario.context.get_open_trades(), [])

            signals = list(strategy.generate_signals(
                scenario.context, history,
            ))
            self.assertEqual(
                [(signal.symbol, signal.side) for signal in signals],
                [("BTC", SignalSide.OPEN_LONG)],
            )
            # Raw signals do not place a 25%-sized order or fill a trade.
            self.assertEqual(scenario.context.get_open_orders(), [])
            self.assertEqual(scenario.context.get_open_trades(), [])
            scenario.check_consistency()

    def test_existing_lot_has_risk_rules_and_generates_an_exit_intent(self):
        strategy = RSIEMAConfluenceStrategy()
        history = genereate_ohlcv_data([100 + i * 0.1 for i in range(100)])
        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            trade = scenario.open_trade(
                "BTC", amount=2, price=100, fee=1,
                opened_at=START - 3 * BAR,
            )
            self.assertEqual(scenario.context.get_unallocated(), 799)
            self.assertEqual(scenario.context.get_position("BTC").cost, 200)
            self.assertEqual(len(trade.stop_losses), 1)
            self.assertEqual(len(trade.take_profits), 1)
            self.assertAlmostEqual(
                trade.stop_losses[0].stop_loss_price, 95,
            )
            self.assertAlmostEqual(
                trade.take_profits[0].take_profit_price, 120,
            )

            scenario.mark_price("BTC", 110, at=START - BAR)
            stored = scenario.context.get_open_trades()[0]
            self.assertEqual(stored.stop_losses[0].high_water_mark, 110)
            self.assertAlmostEqual(
                stored.stop_losses[0].stop_loss_price, 104.5,
            )
            signals = list(strategy.generate_signals(
                scenario.context, history,
            ))
            self.assertEqual(
                [signal.side for signal in signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(scenario.context.get_position("BTC").amount, 2)
            self.assertEqual(scenario.context.get_open_orders(), [])
            self.assertEqual(scenario.now, START)
            scenario.check_consistency()

    def test_pending_reservations_cooldown_history_and_invalid_setup(self):
        strategy = RSIEMAConfluenceStrategy()
        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            scenario.open_trade("BTC", amount=2, price=100, fee=1)
            buy = scenario.place_order(
                "BTC", side="BUY", amount=1, price=90,
            )
            sell = scenario.place_order(
                "BTC", side="SELL", amount=0.5, price=110,
            )
            scenario.record_cooldown(
                "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
            )
            self.assertEqual(scenario.context.get_unallocated(), 709)
            self.assertEqual(
                scenario.context.get_position("BTC").long_amount, 1.5,
            )
            self.assertEqual(
                scenario.context.get_open_trades()[0].available_amount,
                1.5,
            )
            self.assertSetEqual(
                {order.id for order in scenario.context.get_open_orders()},
                {buy.id, sell.id},
            )
            with self.assertRaisesRegex(
                ScenarioSetupError, "Raise initial_cash",
            ):
                scenario.open_trade("BTC", amount=8, price=100)
            self.assertEqual(scenario.context.get_unallocated(), 709)
            scenario.check_consistency()
            # Seeding cooldown history does not advance time or execute it.
            self.assertEqual(scenario.now, START)


if __name__ == "__main__":
    unittest.main(verbosity=2)
