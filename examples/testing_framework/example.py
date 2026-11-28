"""Runnable reference for QuantOS scenario-based strategy regression tests.

Run from the repository root with the project's dependencies installed::

    python -m unittest examples.testing_framework.example -v

Each test constructs a fresh strategy and an isolated StrategyScenario.
The context manager owns an in-memory portfolio and cleans it up on exit;
these examples require no exchange connection or persistent database.
The socket guard below also fails a test if it attempts network access.

Choose the level of evaluation your assertion needs:

* Seed state with open_trade (returns a Trade), register_position (returns
  a Position), or place_order (returns a pending Order). These calls use
  production accounting, rather than inventing cash and holdings separately.
* Inspect configuration with get_*_rule/get_cooldown_rules. Use preview_*
  for hypothetical sizing, eligibility, risk prices, or cooldown blocking.
  Previews neither create orders nor advance time. preview_order evaluates
  an explicit intent; it does not calculate indicators or generate signals.
* Call generate_signals directly to test indicator/confluence decisions
  without the order pipeline. A raw signal is not an approved or filled order.
* Register generated OHLCV data and call step/advance_bars to exercise the
  scheduled strategy pipeline, protective exits, and subsequent fills.
  Existing orders/protection are evaluated before the strategy each step.

Time, data, and units:
    START is timezone-aware UTC; BAR matches this strategy's 2-hour schedule.
    Candle timestamps denote opening times, so a candle becomes usable at
    timestamp + BAR. Include indicator warmup history before START.
    StrategyScenario accepts start or its alias start_date; end_date is an
    inclusive limit, and None (or omission) permits unbounded stepping.
    The first step is strictly after the initial time, not at START.
    Prices, fees, and quote_amount are in EUR; amount is in asset units.
    Pass prices={"ETH": ...} when a preview must value another held/ordered
    asset. Generated execution requires declared OHLCV sources for such
    assets; an offline price mapping is not a substitute for execution data.

Queries and assertions:
    get_trades/get_orders accept Context-compatible filters plus position=.
    Filters intersect; opened_since is inclusive, and portfolio accepts an
    object or ID. Omitting status includes historical as well as open rows.
    Fetch again after a step to inspect current state: returned models/results
    are snapshots, not live views. check_consistency verifies cash, lots,
    holdings, and reservations; it does not assert signal quality or profit.

These deterministic fixtures are regression examples, not investment advice
or evidence that this RSI/EMA strategy is profitable in real markets.
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


# A fixed aware clock makes test outcomes independent of the wall clock.
START = datetime(2025, 1, 15, tzinfo=timezone.utc)
BAR = timedelta(hours=2)


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate causal RSI/EMA columns over the supplied candle history.

    Args:
        data: Chronological OHLCV frame with a numeric Close column.

    Returns:
        A frame retaining OHLCV and adding rsi, ema_20, ema_50, ema_spread.
        Initial warmup rows may not have usable indicator values.

    Trailing indicators use past/current closes, not future rows. This
    whole-frame callable is suitable for the configured precompute mode;
    model/code providers should likewise avoid future-data leakage.
    """
    data = rsi(data, source_column="Close", period=14, result_column="rsi")
    data = ema(data, source_column="Close", period=20, result_column="ema_20")
    data = ema(data, source_column="Close", period=50, result_column="ema_50")
    data["ema_spread"] = data["ema_20"] - data["ema_50"]
    return data


class RSIEMAConfluenceStrategy(ConfluenceScoringStrategy):
    """Long-only BTC/EUR strategy used by every independent scenario.

    Entry requires RSI(14) <= 30 AND EMA(20) > EMA(50).
    Exit requires RSI(14) >= 70 OR EMA(20) < EMA(50).
    Default sizing requests 25% of portfolio value, subject to execution
    constraints. Protection is a 5% trailing stop and a fixed 20% profit
    target, each covering the whole lot. A buy blocks further buys for
    three strategy bars; it does not block sell-side exits.

    Tests may override configuration in the constructor to isolate one
    behavior, without replacing the production confluence/order machinery.
    """
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        # Source IDs key callback dictionaries; symbols name market pairs.
        # pandas=True matches the DataFrame operations in our calculator.
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
        # One calculator supplies two outputs to the confluence cards.
        # Warmup is needed even when a scenario tests only a few new bars.
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
            # Two unit-weight confirmations implement AND.
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
            # One unit-weight confirmation implements OR.
            group_thresholds={"primary": 1},
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC",
            percentage_threshold=5,
            sell_percentage=100,
            trailing=True,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC",
            percentage_threshold=20,
            sell_percentage=100,
        ),
    ]
    cooldowns = [
        CooldownRule(
            symbol="BTC",
            trigger="buy",
            blocks="buy",
            bars=3,
        ),
    ]


def genereate_ohlcv_data(close):
    """Build a whole-strategy data mapping from synthetic closing prices.

    Args:
        close: Ordered sequence of positive prices; these fixtures use
            prices above 1 so Low = Close - 1 remains positive.

    Returns:
        {"btc_2h": frame}, with UTC opening timestamps and canonical OHLCV
        columns. The last candle opens at START - BAR and closes at START.

    Supply enough prices for the strategy's 50-bar minimum history.
    Equal opens/closes and constant volume deliberately keep these fixtures
    simple; they are not intended to reproduce realistic intrabar paths.
    """
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


def generate_scenario_data(at: datetime):
    """Supply cumulative, completed market history at an evaluation time.

    Args:
        at: Aware datetime passed by the scenario, at or after START.

    Returns:
        A mapping keyed by btc_2h containing warmup and all new candles
        completed by at, rather than only the latest candle.

    Raises:
        ValueError: If at precedes the fixture's initial time.

    The warmup's pullback produces an entry setup; a later rise to 230
    produces an exit setup. Rebuilding this deterministic history lets
    indicators and the fill evaluator inspect the required prior candles.
    The callback creates input data only and must not mutate the scenario.
    """
    history = genereate_ohlcv_data(
        [100 + i for i in range(100)]
        + [199 - i * 0.5 for i in range(20)],
    )["btc_2h"]
    # Count closes, not openings: no partial candle is exposed to a decision.
    completed_bars = (at - START) // BAR
    if completed_bars < 0:
        raise ValueError("Scenario data starts at START")
    if completed_bars == 0:
        return {"btc_2h": history}
    close = [189.] + [230.] * (completed_bars - 1)
    opened = [189.5] + close[:-1]
    candles = pd.DataFrame({
        "Open": opened,
        "High": [max(a, b) + 1 for a, b in zip(opened, close)],
        "Low": [min(a, b) - 1 for a, b in zip(opened, close)],
        "Close": close,
        "Volume": [1_000.] * completed_bars,
    }, index=pd.date_range(START, periods=completed_bars, freq="2h"))
    return {"btc_2h": pd.concat([history, candles])}


class TestConfluenceStrategyScenario(unittest.TestCase):
    """Copy individual tests as templates for your strategy's invariants.

    Each test follows arrange (strategy/data/state), act (preview or step),
    and assert (signals, orders, accounting). Always use a fresh strategy
    instance per scenario; do not share mutable cooldown or trade state.
    """

    def setUp(self):
        """Reject accidental network access and restore patches per test."""
        for target in ("socket.socket.connect", "socket.create_connection"):
            patcher = patch(
                target,
                side_effect=AssertionError("This example must stay offline"),
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_initialization(self):
        """Inspect configuration and hypothetical orders on a flat portfolio.

        Raw sizing requests 250 EUR at a 100 EUR/BTC price, or 2.5 BTC.
        The order preview applies eligibility and budgets, while separate
        risk previews model a hypothetical fill. No trade is seeded here:
        detached risk models can be inspected without attaching real rules.
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

            # Configuration describes percentages; previews turn those
            # percentages into concrete prices and quantities for a fill.
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

            # A configured cooldown is not automatically an active cooldown.
            self.assertEqual(scenario.get_cooldown_rules("BTC")[0].bars, 3)
            cooldown = scenario.preview_cooldown("BTC")
            self.assertFalse(cooldown.blocked)
            self.assertEqual(cooldown.remaining_bars, 0)
            self.assertEqual(scenario.context.get_open_orders(), [])
            self.assertEqual(scenario.context.get_trades(), [])
            scenario.check_consistency()

    def test_cooldown_preview_does_not_consume_history(self):
        """Seed emission history and inspect the next decision repeatedly.

        bars_ago is strategy-bar history, not a timedelta or a clock change.
        A buy one bar before the next evaluation leaves two blocked bars
        under this three-bar rule. Repeating previews must not age it.
        """
        strategy = RSIEMAConfluenceStrategy()

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:

            scenario.record_cooldown(
                "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
            )

            for _ in range(2):
                cooldown = scenario.preview_cooldown("BTC")

                # Inspect next-bar eligibility, without running that bar.
                self.assertTrue(cooldown.blocked)

                self.assertEqual(cooldown.remaining_bars, 2)

                # The same history gates an explicit long-order preview.
                self.assertFalse(scenario.preview_order(
                    "BTC", price=100,
                ).approved)

            # Previews do not consume bars. This buy-blocking rule still
            # permits sell-side signals.
            self.assertFalse(scenario.preview_cooldown(
                "BTC", side=SignalSide.CLOSE_LONG,
            ).blocked)
            self.assertEqual(scenario.now, START)

            scenario.check_consistency()

    def test_sizing_override_is_used_by_the_scenario(self):
        """Verify that previews honor a context-dependent sizing override.

        The override requests 10% of unallocated cash. Reserving 400 EUR
        for an ETH order changes the requested BTC allocation from 100
        to 60 EUR. This tests dynamic calculation, not a fixed constant.
        """

        class DynamicStrategy(RSIEMAConfluenceStrategy):
            """Size entries from currently spendable scenario cash."""

            def get_position_size(self, symbol):
                """Return a rule, not a precomputed asset-unit quantity."""
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

            # A pending BUY reserves cash even though it is not yet filled.
            scenario.place_order("ETH", side="BUY", amount=4, price=100)

            self.assertAlmostEqual(scenario.context.get_unallocated(), 600)
            # Additional assets need explicit offline quote prices during
            # portfolio-aware previews, even when the target is BTC.
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
        """Distinguish a sizing request, a budgeted intent, and a gate.

        The strategy still requests 250 EUR after ETH reserves 900 EUR.
        The first BTC preview is reduced to the 100 EUR available budget.
        After a BTC order is seeded, an open-order conflict blocks another
        BTC entry; the trace names that gate, rather than a cash failure.
        """
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

            # This second preview is blocked by the existing BTC order,
            # not simply by the remaining 50 EUR cash balance.
            self.assertFalse(blocked.approved)
            self.assertIn(
                "resolve_conflicts.blocked_open_order", dict(blocked.traces),
            )
            self.assertEqual(scenario.context.get_unallocated(), 50)
            scenario.check_consistency()

    def test_flat_portfolio_generates_an_entry_intent(self):
        """Test only indicator/confluence signal generation on warmup data.

        The rise followed by a pullback supplies both entry confirmations.
        Calling generate_signals directly deliberately bypasses sizing,
        conflict resolution, budgets, emission, and simulated fills.
        Use step instead when the assertion concerns execution.
        """
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

    def test_generated_context_advances_bars_and_fills_orders(self):
        """Run a bounded entry-to-exit lifecycle with generated candles.

        Disabling protection/cooldowns isolates confluence execution.
        Three scheduled decisions demonstrate pending entry, entry fill
        plus exit emission, then exit fill. Step results contain detached
        raw signals, new orders, fills, and production diagnostic traces.
        A signal candle cannot retroactively fill its newly created order.
        """
        strategy = RSIEMAConfluenceStrategy(
            stop_losses=[], take_profits=[], cooldowns=[],
        )
        with StrategyScenario(
            strategy,
            initial_cash=1_000,
            trading_symbol="EUR",
            data_generator=generate_scenario_data,
            start_date=START,
            # Inclusive: the third scheduled evaluation is still allowed.
            end_date=START + 3 * BAR,
        ) as scenario:
            entry = scenario.step()
            self.assertEqual(entry.datetime, START + BAR)
            self.assertEqual(
                [signal.side for signal in entry.signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(entry.orders[0].status, "OPEN")
            self.assertEqual(entry.filled_orders, ())

            # The entry fills on the next completed candle; that step
            # also emits an exit, which fills on the following step.
            exit_step, final = scenario.advance_bars(2)
            self.assertEqual(
                exit_step.filled_orders[0].id, entry.orders[0].id,
            )
            self.assertEqual(
                [signal.side for signal in exit_step.signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(
                final.filled_orders[0].id, exit_step.orders[0].id,
            )
            self.assertEqual(scenario.now, START + 3 * BAR)
            self.assertEqual(scenario.context.get_open_trades(), [])
            self.assertEqual(scenario.context.get_open_orders(), [])
            self.assertAlmostEqual(
                scenario.context.get_unallocated(), 750 + (250 / 189) * 230,
            )
            # Bounds reject further advancement instead of silently ending
            # or forcing liquidation. Omit end_date for an unbounded run.
            with self.assertRaisesRegex(ScenarioSetupError, "end_date"):
                scenario.step()
            scenario.check_consistency()

    def test_existing_lot_has_risk_rules_and_generates_an_exit_intent(self):
        """Seed a historical filled lot, then inspect trailing protection.

        open_trade returns the Trade and applies strategy rules by default.
        The 1 EUR fee reduces cash but is separate from the 200 EUR entry
        cost. A safe historical mark ratchets the trailing stop without
        advancing the clock or placing an exit. Overbought data then yields
        a raw close signal, not an executed liquidation.
        """
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

            # A seeded mark must follow the lot's history, not be in the
            # future, and must not trigger protection. Use steps to test
            # actual stop/take-profit execution.
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
        """Arrange simultaneous cash/unit reservations and invalid seeding.

        A pending BUY reserves quote cash; a pending SELL reserves existing
        asset units and lowers their available amount without filling.
        Seeding does not require an indicator signal or obey its cooldown:
        it deliberately arranges the state whose future behavior is tested.
        Invalid seeding raises ScenarioSetupError before changing balances.
        """
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
            # Assert both the actionable error and unchanged cash. A failed
            # setup must not leave a half-created trade/reservation.
            with self.assertRaisesRegex(
                ScenarioSetupError, "Raise initial_cash",
            ):
                scenario.open_trade("BTC", amount=8, price=100)
            self.assertEqual(scenario.context.get_unallocated(), 709)
            scenario.check_consistency()
            # Seeding cooldown history does not advance time or execute it.
            self.assertEqual(scenario.now, START)

    def test_extreem_crash_scenario(self):
        """Exercise a trailing stop across a price gap using real execution.

        register_position returns the aggregate Position, not a Trade.
        Query its lot and generated opening order, then supply timestamped
        records via a per-symbol callback. A mild rise first ratchets the
        stop to 99.75; the crash emits a protective SELL; a later candle
        fills it at 30 under the production protective-limit behavior.

        Assertions cover protection, no raw long entries, final cash, and
        queryable closed history. A stop threshold is not a guaranteed
        execution price during a gap; realistic execution semantics matter.
        """
        strategy = RSIEMAConfluenceStrategy()
        # Alternating closes make RSI/EMA ready without prematurely
        # producing the overbought exit of a steadily rising warmup.
        warmup = [
            {
                "timestamp": START - (120 - i) * BAR,
                "open": price, "high": price + 1, "low": price - 1,
                "close": price, "volume": 1_000,
            }
            for i, price in enumerate([99, 101] * 60)
        ]
        crash_bars = [
            {
                "timestamp": START, "open": 101, "high": 106,
                "low": 100, "close": 105, "volume": 1_000,
            },
            {
                "timestamp": START + BAR, "open": 105, "high": 106,
                "low": 28, "close": 30, "volume": 1_000,
            },
            {
                "timestamp": START + 2 * BAR, "open": 30, "high": 31,
                "low": 24, "close": 25, "volume": 1_000,
            },
        ]
        candles = warmup + crash_bars

        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR", start=START,
        ) as scenario:
            position = scenario.register_position(
                "BTC", amount=2, price=100, fee=1,
            )

            # All filters intersect. opened_since includes START; portfolio
            # also accepts a Portfolio object. HEDGE queries include both
            # legs unless another filter excludes the associated rows.
            trades = scenario.get_trades(
                position=position,
                target_symbol="BTC",
                trading_symbol="EUR",
                market="BITVAVO",
                portfolio=position.portfolio_id,
                status="OPEN",
                opened_since=START,
            )
            self.assertEqual(len(trades), 1)
            trade = trades[0]

            # The opening order is CLOSED while its Trade remains OPEN:
            # these statuses describe different lifecycle objects.
            orders = scenario.get_orders(
                position=position, target_symbol="BTC", status="CLOSED",
                order_type="LIMIT", order_side="BUY", market="BITVAVO",
            )
            self.assertEqual(len(orders), 1)
            order = orders[0]
            self.assertEqual(order.id, trade.orders[0].id)
            self.assertEqual(order.position_id, position.id)
            self.assertIsNotNone(order.id)
            self.assertEqual(scenario.context.get_unallocated(), 799)

            # "BTC" resolves to the single declared OHLCV source; use
            # "btc_2h" instead when multiple sources make a symbol ambiguous.
            # Return fresh records each call and include only completed bars.
            # Register every source; do not mix per-source registration with
            # a whole-strategy callback such as generate_scenario_data.
            scenario.register_data_generator(
                "BTC", lambda at: (
                    candle for candle in candles
                    if candle["timestamp"] + BAR <= at
                ),
            )

            before_crash = scenario.step()
            self.assertEqual(before_crash.orders, ())
            # Fetch again: the originally returned Trade is not a live view
            # of trailing-rule updates made during execution.
            stored = scenario.context.get_open_trades()[0]
            self.assertAlmostEqual(
                stored.stop_losses[0].stop_loss_price, 99.75,
            )
            # Each step first evaluates existing orders/protection, then
            # runs the strategy. Emission and fill occur on different steps.
            crash, after_crash = scenario.advance_bars(2)
            stop_orders = [
                order for order in crash.orders
                if order.metadata.get("order_reason") == "stop_loss"
            ]
            self.assertEqual(len(stop_orders), 1)
            stop_order = stop_orders[0]
            self.assertEqual(stop_order.order_side, "SELL")
            self.assertEqual(stop_order.amount, 2)
            self.assertEqual(stop_order.status, "OPEN")
            self.assertTrue(
                scenario.context.get_trades()[0].stop_losses[0].triggered,
            )
            self.assertIn(
                stop_order.id,
                [order.id for order in after_crash.filled_orders],
            )
            for result in (before_crash, crash, after_crash):
                self.assertNotIn(
                    SignalSide.OPEN_LONG,
                    [signal.side for signal in result.signals],
                )
            # A crash can gap below the trailing threshold: the production
            # evaluator fills this protective limit at 30, not at 99.75.
            self.assertEqual(after_crash.filled_orders[0].price, 30)
            self.assertEqual(scenario.context.get_unallocated(), 859)
            self.assertEqual(scenario.context.get_open_trades(), [])
            self.assertEqual(scenario.context.get_open_orders(), [])
            # Closed lots/orders remain queryable after liquidation; omit
            # status when inspecting the position's complete history.
            self.assertEqual(
                [trade.id for trade in scenario.get_trades(
                    position=position, status="CLOSED",
                )],
                [trade.id],
            )
            self.assertEqual(
                scenario.get_trades(position=position, status="OPEN"), [],
            )
            self.assertEqual(
                {order.id for order in scenario.get_orders(position=position)},
                {trade.orders[0].id, stop_order.id},
            )
            scenario.check_consistency()


if __name__ == "__main__":
    unittest.main(verbosity=2)
