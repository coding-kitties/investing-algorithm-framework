"""
Tests for STOP and STOP_LIMIT order support (#439).

Covers:
- OrderType.STOP / OrderType.STOP_LIMIT enum
- Order.stop_price / Order.triggered_at fields
- Stop / stop-limit order validation
- Trigger + fill logic in BacktestTradeOrderEvaluator
- Trigger + fill logic in OrderBacktestService.has_executed (legacy path)
"""
import os
from datetime import datetime, timezone

import polars as pl

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
    OrderType,
    TradeStatus,
    BacktestDateRange,
    OrderSide,
)
from investing_algorithm_framework.domain import (
    INDEX_DATETIME,
    Order,
    OperationalException,
)
from investing_algorithm_framework.services import (
    BacktestTradeOrderEvaluator,
    OrderBacktestService,
)
from tests.resources import TestBase

OHLCV_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "resources", "test_data", "ohlcv",
    "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv",
)


class TestStopOrderTypeEnum(TestBase):

    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000000}

    def test_stop_order_type_exists(self):
        self.assertEqual(OrderType.STOP.value, "STOP")
        self.assertEqual(OrderType.STOP_LIMIT.value, "STOP_LIMIT")

    def test_stop_order_type_from_string(self):
        self.assertEqual(OrderType.from_string("STOP"), OrderType.STOP)
        self.assertEqual(
            OrderType.from_string("STOP_LIMIT"), OrderType.STOP_LIMIT
        )

    def test_is_stop_order(self):
        stop = Order(
            order_type=OrderType.STOP.value,
            order_side=OrderSide.SELL.value,
            amount=1.0, target_symbol="BTC", trading_symbol="EUR",
            stop_price=100.0,
        )
        stop_limit = Order(
            order_type=OrderType.STOP_LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1.0, target_symbol="BTC", trading_symbol="EUR",
            stop_price=100.0, price=99.0,
        )
        limit = Order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1.0, target_symbol="BTC", trading_symbol="EUR",
            price=100.0,
        )
        self.assertTrue(stop.is_stop_order())
        self.assertTrue(stop_limit.is_stop_order())
        self.assertFalse(limit.is_stop_order())
        self.assertFalse(stop.is_triggered())


class _StopOrderTestBase(TestBase):
    """Shared setup for evaluator-based stop order tests."""

    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000000}

    def setUp(self):
        super().setUp()
        self.app.container.order_service.override(
            OrderBacktestService(
                trade_service=self.app.container.trade_service(),
                order_repository=self.app.container.order_repository(),
                position_service=self.app.container.position_service(),
                portfolio_repository=(
                    self.app.container.portfolio_repository()
                ),
                portfolio_configuration_service=(
                    self.app.container.portfolio_configuration_service()
                ),
                portfolio_snapshot_service=(
                    self.app.container.portfolio_snapshot_service()
                ),
                configuration_service=(
                    self.app.container.configuration_service()
                ),
            )
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 12, 14),
            end_date=datetime(2023, 12, 25),
        )
        self.app.initialize_backtest_config(backtest_date_range)
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            INDEX_DATETIME,
            datetime(2023, 12, 14, 21, 0, 0, tzinfo=timezone.utc),
        )

        self.ohlcv_df = pl.read_csv(OHLCV_CSV)
        self.ohlcv_df = self.ohlcv_df.with_columns(
            pl.col("Datetime").str.to_datetime().dt.replace_time_zone("UTC")
        )

    def _create_evaluator(self, trading_costs=None):
        return BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
            trade_stop_loss_service=(
                self.app.container.trade_stop_loss_service()
            ),
            trade_take_profit_service=(
                self.app.container.trade_take_profit_service()
            ),
            configuration_service=(
                self.app.container.configuration_service()
            ),
            trading_costs=trading_costs,
        )

    def _buy_position(self, amount, price):
        order_service = self.app.container.order_service()
        order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": amount,
            "order_side": OrderSide.BUY.value,
            "price": price,
            "order_type": OrderType.LIMIT.value,
            "portfolio_id": 1,
            "status": "CREATED",
        })
        order_service.update(order.id, {
            "status": OrderStatus.CLOSED.value,
            "filled": amount,
            "remaining": 0,
        })
        return order


class TestStopOrderValidation(_StopOrderTestBase):

    def test_stop_order_requires_stop_price(self):
        order_service = self.app.container.order_service()
        self._buy_position(0.1, 39000)

        with self.assertRaises(OperationalException):
            order_service.create({
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 0.1,
                "order_side": OrderSide.SELL.value,
                "order_type": OrderType.STOP.value,
                "portfolio_id": 1,
                "status": "CREATED",
            })

    def test_stop_limit_order_requires_stop_and_limit_price(self):
        order_service = self.app.container.order_service()
        self._buy_position(0.1, 39000)

        with self.assertRaises(OperationalException):
            order_service.create({
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 0.1,
                "order_side": OrderSide.SELL.value,
                "order_type": OrderType.STOP_LIMIT.value,
                "portfolio_id": 1,
                "status": "CREATED",
                "stop_price": 38000,
                # missing limit price
            })

    def test_sell_stop_limit_rejects_limit_above_stop(self):
        order_service = self.app.container.order_service()
        self._buy_position(0.1, 39000)

        with self.assertRaises(OperationalException):
            order_service.create({
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 0.1,
                "order_side": OrderSide.SELL.value,
                "order_type": OrderType.STOP_LIMIT.value,
                "portfolio_id": 1,
                "status": "CREATED",
                "stop_price": 38000,
                "price": 38500,  # limit above stop is invalid for SELL
            })


class TestStopOrderFill(_StopOrderTestBase):

    def test_sell_stop_triggers_and_fills_at_stop_price(self):
        """SELL STOP: triggers when Low <= stop_price, then fills as
        a market order at the stop_price (no slippage by default)."""
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        self._buy_position(0.1, 39000)

        # Pick a stop above the lowest low so it triggers in-range
        lowest_low = self.ohlcv_df["Low"].min()
        stop_price = lowest_low + 100  # ensures trigger

        stop_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.SELL.value,
            "order_type": OrderType.STOP.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "stop_price": stop_price,
        })

        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=trade_service.get_all(
                {"status": TradeStatus.OPEN.value}
            ),
            open_orders=order_service.get_all(
                {"status": OrderStatus.OPEN.value}
            ),
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        filled = order_service.get(stop_order.id)
        self.assertEqual(OrderStatus.CLOSED.value, filled.status)
        self.assertEqual(0.1, filled.filled)
        self.assertIsNotNone(filled.triggered_at)
        self.assertEqual(float(filled.price), float(stop_price))

    def test_sell_stop_does_not_trigger_when_price_stays_above(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        self._buy_position(0.1, 39000)

        # Stop well below all lows — should never trigger
        stop_price = float(self.ohlcv_df["Low"].min()) - 10000

        stop_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.SELL.value,
            "order_type": OrderType.STOP.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "stop_price": stop_price,
        })

        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=trade_service.get_all(
                {"status": TradeStatus.OPEN.value}
            ),
            open_orders=order_service.get_all(
                {"status": OrderStatus.OPEN.value}
            ),
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        still_open = order_service.get(stop_order.id)
        self.assertEqual(OrderStatus.OPEN.value, still_open.status)
        self.assertIsNone(still_open.triggered_at)

    def test_sell_stop_limit_triggers_then_fills_at_limit(self):
        """SELL STOP_LIMIT: triggers when Low <= stop_price, then
        becomes a SELL limit order at the limit price."""
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        self._buy_position(0.1, 39000)

        lowest_low = float(self.ohlcv_df["Low"].min())
        highest_high = float(self.ohlcv_df["High"].max())

        # Stop in range so it triggers, limit below stop and below
        # highest high so the limit also fills (SELL limit fills when
        # High >= limit price).
        stop_price = lowest_low + 200
        limit_price = stop_price - 50
        # Sanity: limit_price must be <= highest_high
        self.assertLess(limit_price, highest_high)

        stop_limit_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.SELL.value,
            "order_type": OrderType.STOP_LIMIT.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "stop_price": stop_price,
            "price": limit_price,
        })

        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=trade_service.get_all(
                {"status": TradeStatus.OPEN.value}
            ),
            open_orders=order_service.get_all(
                {"status": OrderStatus.OPEN.value}
            ),
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        filled = order_service.get(stop_limit_order.id)
        self.assertEqual(OrderStatus.CLOSED.value, filled.status)
        self.assertIsNotNone(filled.triggered_at)
        # Fill price for STOP_LIMIT is the limit price
        self.assertEqual(float(filled.price), float(limit_price))
