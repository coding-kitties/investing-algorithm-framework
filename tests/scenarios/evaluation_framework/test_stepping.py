"""Datetime-generated market data drives the real order and fill pipeline."""

from dataclasses import replace
from unittest.mock import patch

import pandas as pd
import polars as pl

from investing_algorithm_framework import (
    CooldownRule, DataSource, OperationalException, PortfolioConfiguration,
    PositionMode,
    ScenarioSetupError, ScenarioStepResult, SignalSide, StopLossRule,
    StrategyScenario,
    TradingCost,
)
from investing_algorithm_framework.domain import (
    INDEX_DATETIME, OrderSide, OrderStatus, OrderType, TradeStatus,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    BAR, START, EvaluationFrameworkTestCase, market_data, scenario,
)


def stepping_data(at):
    history = market_data("entry")["BTC_ohlcv"]
    extra = pd.DataFrame({
        "Open": [189.5, 189, 230, 230],
        "High": [190, 231, 231, 231],
        "Low": [188, 188, 229, 229],
        "Close": [189, 230, 230, 230],
        "Volume": [1_000.] * 4,
    }, index=pd.date_range(START, periods=4, freq="2h"))
    # The scenario must hide incomplete/future rows even if supplied.
    return {"BTC_ohlcv": pd.concat([history, extra])}


class TestStepping(EvaluationFrameworkTestCase):
    def test_register_position_seeds_long_and_short_lots_with_rules(self):
        for direction in ("long", "short"):
            with self.subTest(direction=direction):
                strategy = ConfluenceScoringStrategy(stop_losses=[
                    StopLossRule(5, 100, symbol="BTC", trailing=True),
                ])
                with scenario(
                    strategy, position_mode=PositionMode.HEDGE,
                ) as seeded:
                    position = seeded.register_position(
                        "BTC", amount=2, price=100, fee=1,
                        direction=direction,
                    )
                    trades = seeded.get_trades(position=position)
                    orders = seeded.get_orders(position=position)
                    self.assertEqual(position.symbol, "BTC")
                    self.assertEqual(len(trades), 1)
                    self.assertEqual(len(orders), 1)
                    trade = trades[0]
                    self.assertEqual(orders[0].id, trade.orders[0].id)
                    self.assertEqual(orders[0].position_id, position.id)
                    self.assertIsNotNone(trade.orders[0].id)
                    self.assertEqual(trade.orders[0].status, "CLOSED")
                    self.assertEqual(trade.orders[0].filled, 2)
                    self.assertEqual(trade.orders[0].order_fee, 1)
                    self.assertEqual(trade.is_short, direction == "short")
                    self.assertEqual(
                        trade.stop_losses[0].stop_loss_price,
                        95 if direction == "long" else 105,
                    )
                    self.assertEqual(
                        seeded.context.get_unallocated(),
                        799 if direction == "long" else 1_199,
                    )
                    seeded.check_consistency()

    def test_position_queries_include_multiple_lots_and_both_hedge_legs(self):
        with scenario(
            ConfluenceScoringStrategy(), position_mode=PositionMode.HEDGE,
        ) as seeded:
            position = seeded.register_position("BTC", amount=2, price=100)
            second = seeded.register_position("BTC", amount=1, price=100)
            short = seeded.register_position(
                "BTC", amount=1, price=100, direction="short",
            )
            unrelated = seeded.open_trade("ETH", amount=1, price=50)
            pending = seeded.place_order(
                "BTC", side="SELL", amount=1, price=110,
            )
            self.assertEqual(position.id, second.id)
            self.assertEqual(position.id, short.id)
            trades = seeded.get_trades(position=position)
            self.assertEqual(len(trades), 3)
            self.assertEqual(sum(trade.is_short for trade in trades), 1)
            self.assertNotIn(unrelated.id, [trade.id for trade in trades])
            orders = seeded.get_orders(position=position)
            self.assertEqual(len(orders), 4)
            self.assertIn(pending.id, [order.id for order in orders])
            self.assertTrue(
                all(order.position_id == position.id for order in orders),
            )
            self.assertEqual(len(seeded.get_trades()), 4)
            self.assertEqual(len(seeded.get_orders()), 5)
            seeded.check_consistency()

    def test_position_queries_reject_invalid_positions_and_closed_state(self):
        with scenario(ConfluenceScoringStrategy()) as seeded:
            position = seeded.register_position("BTC", amount=2, price=100)
            trade = seeded.get_trades(position=position)[0]
            for query in (seeded.get_trades, seeded.get_orders):
                with self.subTest(query=query.__name__):
                    with self.assertRaisesRegex(
                        ScenarioSetupError, "must be a Position",
                    ):
                        query(position=trade)
                    invalid = type(position)(symbol="MISSING")
                    with self.assertRaisesRegex(
                        ScenarioSetupError, "does not exist",
                    ):
                        query(position=invalid)
        for query in (seeded.get_trades, seeded.get_orders):
            with self.assertRaises(ScenarioSetupError):
                query(position=position)

    def test_trade_query_filters_and_position_intersection(self):
        with scenario(ConfluenceScoringStrategy()) as seeded:
            position = seeded.register_position(
                "BTC", amount=1, price=100, opened_at=START - BAR,
            )
            older = seeded.get_trades(position=position)[0]
            newer = seeded.open_trade("BTC", amount=1, price=110)
            eth = seeded.open_trade("ETH", amount=1, price=50)
            portfolio = seeded.context.get_portfolios()[0]
            all_ids = {older.id, newer.id, eth.id}
            cases = [
                ({}, all_ids),
                ({"target_symbol": "BTC"}, {older.id, newer.id}),
                ({"trading_symbol": "EUR"}, all_ids),
                ({"market": "BITVAVO"}, all_ids),
                ({"portfolio": portfolio}, all_ids),
                ({"portfolio": portfolio.id}, all_ids),
                ({"status": TradeStatus.OPEN}, all_ids),
                ({"status": "OPEN"}, all_ids),
                ({"status": TradeStatus.CLOSED}, set()),
                ({"opened_since": START - BAR}, all_ids),
                ({"opened_since": START}, {newer.id, eth.id}),
                ({"opened_since": START + BAR}, set()),
                ({"trading_symbol": "USD"}, set()),
                ({"target_symbol": "ETH", "position": position}, set()),
                ({
                    "target_symbol": "BTC", "trading_symbol": "EUR",
                    "market": "BITVAVO", "portfolio": portfolio.id,
                    "status": TradeStatus.OPEN, "opened_since": START,
                    "position": position,
                }, {newer.id}),
                ({"market": "OTHER", "portfolio": portfolio}, set()),
            ]
            for params, expected in cases:
                with self.subTest(params=params):
                    self.assertEqual(
                        {trade.id for trade in seeded.get_trades(**params)},
                        expected,
                    )
            self.assertEqual(
                [trade.id for trade in seeded.get_trades(
                    "BTC", "EUR", "BITVAVO", portfolio, "OPEN", START,
                    position=position,
                )],
                [newer.id],
            )
            self.assertEqual(seeded.now, START)
            self.assertEqual(seeded.context.get_unallocated(), 740)
            seeded.check_consistency()

    def test_order_query_filters_and_position_intersection(self):
        with scenario(ConfluenceScoringStrategy()) as seeded:
            position = seeded.register_position("BTC", amount=2, price=100)
            entry = seeded.get_orders(position=position)[0]
            sell = seeded.place_order("BTC", side="SELL", amount=1, price=110)
            buy = seeded.place_order("ETH", side="BUY", amount=1, price=50)
            all_ids = {entry.id, sell.id, buy.id}
            cases = [
                ({}, all_ids),
                ({"target_symbol": "BTC"}, {entry.id, sell.id}),
                ({"status": OrderStatus.OPEN}, {sell.id, buy.id}),
                ({"status": "CLOSED"}, {entry.id}),
                ({"order_type": OrderType.LIMIT}, all_ids),
                ({"order_type": "LIMIT"}, all_ids),
                ({"order_type": OrderType.MARKET}, set()),
                ({"order_side": OrderSide.SELL}, {sell.id}),
                ({"order_side": "BUY"}, {entry.id, buy.id}),
                ({"market": "BITVAVO"}, all_ids),
                ({"status": OrderStatus.CANCELED}, set()),
                ({"target_symbol": "ETH", "position": position}, set()),
                ({
                    "target_symbol": "BTC", "status": OrderStatus.OPEN,
                    "order_type": "LIMIT", "order_side": OrderSide.SELL,
                    "market": "BITVAVO", "position": position,
                }, {sell.id}),
            ]
            for params, expected in cases:
                with self.subTest(params=params):
                    self.assertEqual(
                        {order.id for order in seeded.get_orders(**params)},
                        expected,
                    )
            self.assertEqual(
                [order.id for order in seeded.get_orders(
                    "BTC", "OPEN", "LIMIT", "SELL", "BITVAVO",
                    position=position,
                )],
                [sell.id],
            )
            self.assertEqual(
                [order.id for order in seeded.get_orders()],
                [order.id for order in seeded.context.get_orders()],
            )
            self.assertEqual(seeded.now, START)
            self.assertEqual(seeded.context.get_unallocated(), 750)
            seeded.check_consistency()

    def test_query_filters_surface_unknown_market_errors(self):
        with scenario(ConfluenceScoringStrategy()) as seeded:
            position = seeded.register_position("BTC", amount=1, price=100)
            for query in (seeded.get_trades, seeded.get_orders):
                with self.subTest(query=query.__name__):
                    with self.assertRaises(OperationalException):
                        query(position=position, market="UNKNOWN")
            self.assertEqual(len(seeded.get_trades(position=position)), 1)
            self.assertEqual(len(seeded.get_orders(position=position)), 1)
            self.assertEqual(seeded.context.get_unallocated(), 900)
            seeded.check_consistency()

    def test_symbol_generator_gets_datetime_and_consumes_records(self):
        strategy = ConfluenceScoringStrategy()
        frame = stepping_data(START)["BTC_ohlcv"].rename_axis("timestamp")
        records = frame.reset_index().rename(
            columns=lambda column: column.lower(),
        ).to_dict("records")
        calls = []

        def generate(at):
            calls.append(at)
            return (
                record for record in records
                if record["timestamp"] + BAR <= at
            )

        with scenario(strategy) as seeded:
            seeded.register_data_generator("btc", generate)
            first, second = seeded.advance_bars(2)
            self.assertEqual(calls, [START + BAR, START + 2 * BAR])
            self.assertEqual(first.orders[0].price, 189)
            self.assertEqual(second.filled_orders[0].id, first.orders[0].id)
            seeded.check_consistency()

    def test_source_id_generators_accept_pandas_and_polars_frames(self):
        for backend in ("pandas", "polars"):
            with self.subTest(backend=backend):
                frame = stepping_data(START)["BTC_ohlcv"].rename_axis(
                    "timestamp",
                ).reset_index().rename(columns=lambda column: column.lower())
                if backend == "polars":
                    frame = pl.from_pandas(frame)
                with scenario(ConfluenceScoringStrategy()) as seeded:
                    seeded.register_data_generator(
                        "BTC_ohlcv", lambda at: frame,
                    )
                    first, second = seeded.advance_bars(2)
                    self.assertEqual(first.orders[0].price, 189)
                    self.assertEqual(
                        second.filled_orders[0].id, first.orders[0].id,
                    )
                    seeded.check_consistency()

    def test_ambiguous_symbols_and_missing_source_ids_are_rejected(self):
        extra_source = DataSource(
            identifier="btc_daily", symbol="BTC/EUR", market="BITVAVO",
            data_type="OHLCV", time_frame="1d", pandas=True,
        )
        strategy = ConfluenceScoringStrategy(data_sources=[
            *ConfluenceScoringStrategy.data_sources, extra_source,
        ])
        frame = stepping_data(START)["BTC_ohlcv"]
        with scenario(strategy) as seeded:
            with self.assertRaisesRegex(ScenarioSetupError, "ambiguous"):
                seeded.register_data_generator("BTC", lambda at: frame)
            seeded.register_data_generator("BTC_ohlcv", lambda at: frame)
            with self.assertRaisesRegex(ScenarioSetupError, "btc_daily"):
                seeded.step()
            self.assertEqual(seeded.now, START)
            daily = frame.resample("1D").agg({
                "Open": "first", "High": "max", "Low": "min",
                "Close": "last", "Volume": "sum",
            })
            seeded.register_data_generator("btc_daily", lambda at: daily)
            self.assertEqual(len(seeded.step().orders), 1)

    def test_symbol_generator_errors_and_incompatible_modes(self):
        with scenario(ConfluenceScoringStrategy()) as seeded:
            with self.assertRaisesRegex(ScenarioSetupError, "callable"):
                seeded.register_data_generator("BTC")
            with self.assertRaisesRegex(ScenarioSetupError, "declared OHLCV"):
                seeded.register_data_generator("ETH", lambda at: [])
            for raw in ("bad", [1], [{"close": 100}]):
                with self.subTest(raw=raw):
                    seeded.register_data_generator("BTC", lambda at: raw)
                    with self.assertRaises(ScenarioSetupError):
                        seeded.step()
                    self.assertEqual(seeded.now, START)
                    self.assertEqual(seeded.context.get_orders(), [])
            with self.assertRaisesRegex(ScenarioSetupError, "mix"):
                seeded.register_data_generator(stepping_data)
        with scenario(
            ConfluenceScoringStrategy(), data_generator=stepping_data,
        ) as seeded:
            with self.assertRaisesRegex(ScenarioSetupError, "mix"):
                seeded.register_data_generator("BTC", lambda at: [])
            self.assertEqual(len(seeded.step().orders), 1)

    def test_start_date_alias_and_inclusive_end_date(self):
        calls = []

        def generate(at):
            calls.append(at)
            return stepping_data(at)

        strategy = ConfluenceScoringStrategy()
        with StrategyScenario(
            strategy, initial_cash=1_000, trading_symbol="EUR",
            start_date=START, end_date=START + 3 * BAR,
            data_generator=generate,
        ) as seeded:
            results = seeded.advance_bars(3)
            self.assertEqual(results[-1].datetime, START + 3 * BAR)
            cash = seeded.context.get_unallocated()
            with self.assertRaisesRegex(ScenarioSetupError, "end_date"):
                seeded.step()
            self.assertEqual(len(calls), 3)
            self.assertEqual(strategy._cooldown_bar_index, 3)
            self.assertEqual(seeded.now, START + 3 * BAR)
            self.assertEqual(seeded.context.get_unallocated(), cash)
            seeded.check_consistency()

    def test_out_of_range_advance_is_rejected_before_any_bar_runs(self):
        calls = []

        def generate(at):
            calls.append(at)
            return stepping_data(at)

        strategy = ConfluenceScoringStrategy()
        with scenario(
            strategy, end_date=START + 2 * BAR, data_generator=generate,
        ) as seeded:
            with self.assertRaisesRegex(ScenarioSetupError, "end_date"):
                seeded.advance_bars(3)
            self.assertEqual(calls, [])
            self.assertEqual(seeded.now, START)
            self.assertEqual(strategy._cooldown_bar_index, 0)
            self.assertEqual(seeded.context.get_orders(), [])
            self.assertEqual(seeded.context.get_unallocated(), 1_000)
            self.assertEqual(len(seeded.advance_bars(2)), 2)
            seeded.check_consistency()

    def test_optional_end_date_and_conflicting_date_arguments(self):
        for arguments in (
            {"start_date": START, "end_date": None},
            {"start": START, "start_date": START},
        ):
            with self.subTest(arguments=arguments):
                with StrategyScenario(
                    ConfluenceScoringStrategy(), initial_cash=1_000,
                    trading_symbol="EUR", data_generator=stepping_data,
                    **arguments,
                ) as seeded:
                    self.assertEqual(len(seeded.advance_bars(4)), 4)
                    self.assertEqual(seeded.now, START + 4 * BAR)
        for arguments, message in (
            ({}, "start"),
            ({"start": START, "start_date": START + BAR}, "same time"),
            ({"start_date": START, "end_date": START - BAR}, "at or after"),
            (
                {"start_date": START, "end_date": START.replace(tzinfo=None)},
                "timezone-aware",
            ),
            ({"start_date": START, "end_date": "invalid"}, "timezone-aware"),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ScenarioSetupError, message):
                    StrategyScenario(
                        ConfluenceScoringStrategy(), initial_cash=1_000,
                        trading_symbol="EUR", **arguments,
                    )

    def test_datetime_callback_drives_entry_exit_and_later_candle_fills(self):
        strategy = ConfluenceScoringStrategy()
        original_context = strategy.context
        calls = []

        def generate(at):
            calls.append(at)
            return stepping_data(at)

        with scenario(strategy, data_generator=generate) as seeded:
            first = seeded.step()
            self.assertIsInstance(first, ScenarioStepResult)
            self.assertEqual(first.datetime, START + BAR)
            self.assertEqual(
                [signal.side for signal in first.signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(len(first.orders), 1)
            self.assertEqual(first.orders[0].status, "OPEN")
            self.assertAlmostEqual(first.orders[0].price, 189)
            self.assertAlmostEqual(first.orders[0].amount, 250 / 189)
            self.assertEqual(first.filled_orders, ())
            self.assertEqual(seeded.context.get_open_trades(), [])
            self.assertAlmostEqual(seeded.context.get_unallocated(), 750)

            second, third = seeded.advance_bars(2)
            self.assertEqual(len(second.filled_orders), 1)
            self.assertEqual(second.filled_orders[0].id, first.orders[0].id)
            self.assertEqual(second.filled_orders[0].status, "CLOSED")
            self.assertEqual(
                [signal.side for signal in second.signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(second.orders[0].order_side, "SELL")
            self.assertEqual(second.orders[0].status, "OPEN")
            self.assertEqual(third.filled_orders[0].id, second.orders[0].id)
            self.assertEqual(third.orders, ())
            self.assertEqual(seeded.context.get_open_trades(), [])
            self.assertEqual(seeded.context.get_open_orders(), [])
            self.assertAlmostEqual(
                seeded.context.get_unallocated(), 750 + 250 / 189 * 230,
            )
            self.assertEqual(seeded.context.get_latest_price("BTC/EUR"), 230)
            self.assertEqual(seeded.now, START + 3 * BAR)
            self.assertEqual(calls, [START + i * BAR for i in (1, 2, 3)])
            self.assertEqual(strategy._cooldown_bar_index, 3)
            self.assertIs(strategy.context, original_context)
            self.assertEqual(first.orders[0].status, "OPEN")
            self.assertEqual(second.orders[0].status, "OPEN")
            seeded.check_consistency()

    def test_seeded_cooldown_expires_only_on_scheduled_evaluations(self):
        strategy = ConfluenceScoringStrategy(cooldowns=[
            CooldownRule(symbol="BTC", trigger="buy", blocks="buy", bars=3),
        ])
        history = stepping_data(START)["BTC_ohlcv"].iloc[:121]
        closes = history["Close"].iloc[-1]
        extra = pd.DataFrame({
            column: [closes] * 4 for column in ("Open", "High", "Low", "Close")
        }, index=pd.date_range(START + BAR, periods=4, freq="2h"))
        extra["Volume"] = 1_000.
        full = pd.concat([history, extra])
        with scenario(strategy) as seeded:
            seeded.register_data_generator(lambda at: {"BTC_ohlcv": full})
            seeded.record_cooldown(
                "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
            )
            first, second, third = seeded.advance_bars(3)
            self.assertEqual(first.orders, ())
            self.assertEqual(second.orders, ())
            self.assertEqual(len(third.orders), 1)
            self.assertEqual(strategy._cooldown_bar_index, 3)
            self.assertTrue(seeded.preview_cooldown("BTC").blocked)
            seeded.check_consistency()

    def test_limit_order_stays_pending_when_later_candles_do_not_match(self):
        strategy = ConfluenceScoringStrategy()
        data = stepping_data(START)["BTC_ohlcv"]
        data.loc[START + BAR, ["Open", "Low"]] = [230, 229]
        with scenario(strategy) as seeded:
            seeded.register_data_generator(lambda at: {"BTC_ohlcv": data})
            first, second = seeded.advance_bars(2)
            self.assertEqual(second.filled_orders, ())
            self.assertEqual(seeded.context.get_open_trades(), [])
            self.assertEqual(seeded.context.get_open_orders()[0].id,
                             first.orders[0].id)
            self.assertEqual(seeded.context.get_unallocated(), 750)
            seeded.check_consistency()

    def test_seeded_stop_loss_creates_a_protective_exit_and_fills_later(self):
        strategy = ConfluenceScoringStrategy(
            stop_losses=[StopLossRule(5, 100, symbol="BTC")],
        )
        with scenario(strategy) as seeded:
            seeded.open_trade("BTC", amount=1, price=200)
            seeded.register_data_generator(stepping_data)
            first = seeded.step()
            exits = [
                order for order in first.orders
                if order.metadata.get("order_reason") == "stop_loss"
            ]
            self.assertEqual(len(exits), 1)
            self.assertEqual(exits[0].order_side, "SELL")
            second = seeded.step()
            self.assertIn(
                exits[0].id, [order.id for order in second.filled_orders],
            )
            seeded.check_consistency()

    def test_trading_costs_and_hooks_use_the_production_evaluator(self):
        class HookedConfluence(ConfluenceScoringStrategy):
            def on_trade_opened(self, context, trade):
                self.opened_trade = trade.id
                self.hook_time = context.config[INDEX_DATETIME]

        strategy = HookedConfluence()
        configuration = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR",
            trading_costs=[TradingCost(symbol="BTC", fee_percentage=1)],
        )
        with StrategyScenario(
            strategy, initial_cash=1_000, start=START,
            portfolio_configuration=configuration,
        ) as seeded:
            seeded.register_data_generator(stepping_data)
            first, second = seeded.advance_bars(2)
            self.assertAlmostEqual(second.filled_orders[0].order_fee, 2.5)
            self.assertAlmostEqual(seeded.context.get_unallocated(), 747.5)
            self.assertEqual(
                strategy.opened_trade, seeded.context.get_trades()[0].id,
            )
            self.assertEqual(strategy.hook_time, START + 2 * BAR)
            self.assertEqual(first.orders[0].order_fee or 0, 0)
            seeded.check_consistency()

    def test_polars_generator_and_hedge_short_pending_fill(self):
        strategy = ConfluenceScoringStrategy(confluence_cards=[
            replace(
                ConfluenceScoringStrategy.confluence_cards[0],
                side=SignalSide.OPEN_SHORT,
            ),
        ])

        def generate(at):
            frame = stepping_data(at)["BTC_ohlcv"].copy()
            frame.index.name = "Datetime"
            return {"BTC_ohlcv": pl.from_pandas(frame.reset_index())}

        with scenario(strategy, position_mode=PositionMode.HEDGE) as seeded:
            seeded.register_data_generator(generate)
            first, second = seeded.advance_bars(2)
            self.assertEqual(first.orders[0].order_side, "SHORT")
            self.assertEqual(len(second.filled_orders), 1)
            self.assertTrue(seeded.context.get_open_trades()[0].is_short)
            seeded.check_consistency()

    def test_bad_data_or_generator_errors_do_not_advance_the_scenario(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            for generator, error in (
                (lambda at: None, ScenarioSetupError),
                (lambda at: {}, ScenarioSetupError),
                (lambda at: {"wrong_id": pd.DataFrame()}, ScenarioSetupError),
                (lambda at: {"BTC_ohlcv": "invalid"}, ScenarioSetupError),
            ):
                with self.subTest(generator=generator):
                    seeded.register_data_generator(generator)
                    with self.assertRaises(error):
                        seeded.step()
                    self.assertEqual(seeded.now, START)
                    self.assertEqual(strategy._cooldown_bar_index, 0)
                    self.assertEqual(seeded.context.get_orders(), [])
            broken = stepping_data(START)["BTC_ohlcv"]
            broken.iloc[0, broken.columns.get_loc("High")] = 0
            seeded.register_data_generator(lambda at: {"BTC_ohlcv": broken})
            with self.assertRaisesRegex(ScenarioSetupError, "invalid OHLCV"):
                seeded.step()

            def failing(at):
                raise ValueError("generator failed")

            seeded.register_data_generator(failing)
            with self.assertRaisesRegex(ValueError, "generator failed"):
                seeded.step()
            self.assertEqual(seeded.now, START)
            seeded.register_data_generator(stepping_data)
            self.assertEqual(len(seeded.step().orders), 1)

    def test_missing_asset_data_is_not_fetched_and_time_is_unchanged(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            seeded.place_order("ETH", side="BUY", amount=1, price=100)
            seeded.register_data_generator(stepping_data)
            with self.assertRaisesRegex(ScenarioSetupError, "ETH/EUR"):
                seeded.step()
            self.assertEqual(seeded.now, START)
            self.assertEqual(strategy._cooldown_bar_index, 0)
            self.assertEqual(seeded.context.get_unallocated(), 900)
            seeded.check_consistency()

    def test_steps_preserve_isolation_and_seed_clock_after_advancing(self):
        with scenario(ConfluenceScoringStrategy()) as first, \
                scenario(ConfluenceScoringStrategy()) as second:
            first.register_data_generator(stepping_data)
            second.register_data_generator(stepping_data)
            first.step()
            self.assertEqual(second.now, START)
            self.assertEqual(second.context.get_orders(), [])
            result = second.step()
            self.assertEqual(len(result.orders), 1)
            first.open_trade(
                "BTC", amount=0.1, price=189,
            )
            self.assertEqual(first.now, START + BAR)
            self.assertEqual(first.preview_order(
                "BTC", price=189,
            ).orders, ())
            first.check_consistency()
            second.check_consistency()

    def test_evaluation_failure_restores_binding_and_blocks_retry(self):
        strategy = ConfluenceScoringStrategy()
        original = strategy.context
        with scenario(strategy) as seeded:
            seeded.register_data_generator(stepping_data)
            with patch.object(
                strategy.executor, "execute",
                side_effect=RuntimeError("executor failed"),
            ):
                with self.assertLogs(
                    "investing_algorithm_framework", level="ERROR",
                ):
                    with self.assertRaisesRegex(
                        OperationalException, "executor failed",
                    ):
                        seeded.step()
            self.assertIs(strategy.context, original)
            with self.assertRaisesRegex(ScenarioSetupError, "failed"):
                seeded.step()

    def test_step_registration_and_count_validation(self):
        with self.assertRaisesRegex(ScenarioSetupError, "callable"):
            scenario(ConfluenceScoringStrategy(), data_generator=42)
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            with self.assertRaisesRegex(ScenarioSetupError, "Register"):
                seeded.step()
            with self.assertRaisesRegex(ScenarioSetupError, "callable"):
                seeded.register_data_generator(None)
            for count in (0, -1, True, 1.5):
                with self.subTest(count=count):
                    with self.assertRaises(ScenarioSetupError):
                        seeded.advance_bars(count)
            seeded.register_data_generator(stepping_data)
        with self.assertRaisesRegex(ScenarioSetupError, "closed"):
            seeded.step()
