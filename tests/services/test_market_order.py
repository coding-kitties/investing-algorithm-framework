"""
Tests for market order support (#430).

Covers:
- OrderType.MARKET enum
- Market order creation via context API
- Market order validation
- Market order fill logic in BacktestTradeOrderEvaluator
  (fills at next candle open + slippage, reconciles portfolio)
- Order.estimated_price property
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
    TradingCost,
)
from investing_algorithm_framework.services import (
    BacktestTradeOrderEvaluator,
    OrderBacktestService,
)
from tests.resources import TestBase

# Path to OHLCV CSV used by these tests (BTC-EUR, 15m, Binance)
OHLCV_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "resources", "test_data", "ohlcv",
    "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv",
)


class TestOrderTypeEnum(TestBase):
    """Test that OrderType.MARKET is recognized."""

    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
        )
    ]
    external_balances = {"EUR": 1000000}

    def test_market_order_type_exists(self):
        self.assertEqual(OrderType.MARKET.value, "MARKET")

    def test_market_order_type_from_string(self):
        self.assertEqual(
            OrderType.from_string("MARKET"), OrderType.MARKET
        )

    def test_market_order_type_equals(self):
        self.assertTrue(OrderType.MARKET.equals("MARKET"))
        self.assertFalse(OrderType.MARKET.equals("LIMIT"))


class TestOrderEstimatedPrice(TestBase):
    """Test Order.estimated_price property via metadata."""

    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
        )
    ]
    external_balances = {"EUR": 1000000}

    def test_estimated_price_getter_and_setter(self):
        order = Order(
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.BUY.value,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="EUR",
        )
        self.assertIsNone(order.estimated_price)
        order.estimated_price = 100.0
        self.assertEqual(order.estimated_price, 100.0)
        self.assertEqual(order.metadata["estimated_price"], 100.0)

    def test_get_size_with_estimated_price(self):
        """When price is None, get_size should fall back to
        estimated_price."""
        order = Order(
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.BUY.value,
            amount=2.0,
            price=None,
            target_symbol="BTC",
            trading_symbol="EUR",
            metadata={"estimated_price": 50.0},
        )
        self.assertEqual(order.get_size(), 100.0)

    def test_get_size_prefers_real_price(self):
        """When price is set, get_size should use it, not
        estimated_price."""
        order = Order(
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.BUY.value,
            amount=2.0,
            price=60.0,
            target_symbol="BTC",
            trading_symbol="EUR",
            metadata={"estimated_price": 50.0},
        )
        self.assertEqual(order.get_size(), 120.0)


class TestMarketOrderCreation(TestBase):
    """Test market order creation via order service."""

    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
        )
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

    def test_create_market_buy_order(self):
        """Market buy order is created with estimated_price in
        metadata and status OPEN."""
        order_service = self.app.container.order_service()
        order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.BUY.value,
            "price": 39000,  # estimated price
            "order_type": OrderType.MARKET.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "metadata": {"estimated_price": 39000},
        })
        self.assertEqual(OrderType.MARKET.value, order.order_type)
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(39000, order.estimated_price)

    def test_create_market_sell_order(self):
        """Market sell order is created after buying a position."""
        order_service = self.app.container.order_service()

        # First create a buy to have a position
        buy_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.BUY.value,
            "price": 39000,
            "order_type": OrderType.LIMIT.value,
            "portfolio_id": 1,
            "status": "CREATED",
        })
        # Fill the buy order
        order_service.update(buy_order.id, {
            "status": OrderStatus.CLOSED.value,
            "filled": 0.1,
            "remaining": 0,
        })

        # Now create market sell
        sell_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.1,
            "order_side": OrderSide.SELL.value,
            "price": 39000,
            "order_type": OrderType.MARKET.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "metadata": {"estimated_price": 39000},
        })
        self.assertEqual(OrderType.MARKET.value, sell_order.order_type)
        self.assertEqual(OrderStatus.OPEN.value, sell_order.status)


class TestMarketOrderFill(TestBase):
    """Test market order fill in BacktestTradeOrderEvaluator.

    Market orders should fill at the Open price of the first candle
    after order.updated_at, with slippage applied.
    """

    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
        )
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
            pl.col("Datetime")
            .str.to_datetime()
            .dt.replace_time_zone("UTC")
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

    def _create_pending_market_buy_order(
        self, target_symbol, estimated_price, amount
    ):
        order_service = self.app.container.order_service()
        return order_service.create({
            "target_symbol": target_symbol,
            "trading_symbol": "EUR",
            "amount": amount,
            "order_side": OrderSide.BUY.value,
            "price": estimated_price,
            "order_type": OrderType.MARKET.value,
            "portfolio_id": 1,
            "status": "CREATED",
            "metadata": {"estimated_price": estimated_price},
        })

    def test_market_buy_order_fills_at_open_price(self):
        """Market buy order fills at the Open of the first available
        candle."""
        order = self._create_pending_market_buy_order("BTC", 39000, 0.1)
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        open_orders = order_service.get_all(
            {"status": OrderStatus.OPEN.value}
        )
        self.assertEqual(1, len(open_orders))

        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=trade_service.get_all(
                {"status": TradeStatus.OPEN.value}
            ),
            open_orders=open_orders,
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        # Order should be filled
        filled_order = order_service.get(order.id)
        self.assertEqual(OrderStatus.CLOSED.value, filled_order.status)
        self.assertEqual(0.1, filled_order.filled)
        self.assertEqual(0, filled_order.remaining)

        # Fill price should be the Open of the first candle
        first_candle_open = self.ohlcv_df.head(1)["Open"][0]
        self.assertEqual(filled_order.price, first_candle_open)

    def test_market_buy_order_fills_with_slippage(self):
        """Market buy order fill price includes slippage from
        TradingCost."""
        slippage_pct = 0.1  # 0.1%
        tc = TradingCost(
            symbol="BTC",
            slippage_percentage=slippage_pct,
        )

        order = self._create_pending_market_buy_order("BTC", 39000, 0.1)
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        evaluator = self._create_evaluator(trading_costs=[tc])
        evaluator.evaluate(
            open_trades=trade_service.get_all(
                {"status": TradeStatus.OPEN.value}
            ),
            open_orders=order_service.get_all(
                {"status": OrderStatus.OPEN.value}
            ),
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        filled_order = order_service.get(order.id)
        first_candle_open = self.ohlcv_df.head(1)["Open"][0]
        expected_fill = first_candle_open * (1 + slippage_pct / 100)
        self.assertAlmostEqual(
            filled_order.price, expected_fill, places=2
        )
        # Slippage should be fill_price - base_price
        self.assertAlmostEqual(
            filled_order.slippage,
            expected_fill - first_candle_open,
            places=2,
        )

    def test_market_order_reconciles_portfolio(self):
        """When the fill price differs from the estimated price,
        the portfolio unallocated balance is adjusted."""
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        portfolio_repo = self.app.container.portfolio_repository()

        # Get initial unallocated balance
        portfolio_before = portfolio_repo.get(1)

        # Create order with estimated_price different from what
        # the open will be
        estimated_price = 35000  # intentionally different from actual
        order = self._create_pending_market_buy_order(
            "BTC", estimated_price, 0.1
        )

        # Record unallocated after order creation (cash reserved
        # at estimated_price)
        portfolio_after_create = portfolio_repo.get(1)
        reserved = estimated_price * 0.1

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

        # After fill, the portfolio should be reconciled
        portfolio_after_fill = portfolio_repo.get(1)
        filled_order = order_service.get(order.id)
        actual_fill_price = filled_order.price

        # The reconciliation adjusts by (fill_price - estimated) * amount
        # So final unallocated = after_create - delta
        delta = (actual_fill_price - estimated_price) * 0.1
        expected_unallocated = \
            portfolio_after_create.get_unallocated() - delta

        self.assertAlmostEqual(
            portfolio_after_fill.get_unallocated(),
            expected_unallocated,
            places=2,
        )

    def test_market_order_creates_trade(self):
        """A trade is created for the market order."""
        order = self._create_pending_market_buy_order("BTC", 39000, 0.1)
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

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

        # Trade should exist and be OPEN
        trade = trade_service.find({"order_id": order.id})
        self.assertIsNotNone(trade)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)


class TestMarketOrderValidation(TestBase):
    """Test market order validation."""

    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
        )
    ]
    external_balances = {"EUR": 1000}

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

    def test_market_buy_order_exceeding_balance_raises(self):
        """Market buy order that exceeds portfolio balance should
        raise an error."""
        order_service = self.app.container.order_service()

        with self.assertRaises(Exception):
            order_service.create({
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 100,  # 100 BTC * 39000 >> 1000 EUR balance
                "order_side": OrderSide.BUY.value,
                "price": 39000,
                "order_type": OrderType.MARKET.value,
                "portfolio_id": 1,
                "status": "CREATED",
                "metadata": {"estimated_price": 39000},
            })

    def test_market_sell_order_exceeding_position_raises(self):
        """Market sell order that exceeds position should raise."""
        order_service = self.app.container.order_service()

        # Buy a small amount first
        buy = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 0.01,
            "order_side": OrderSide.BUY.value,
            "price": 100,
            "order_type": OrderType.LIMIT.value,
            "portfolio_id": 1,
            "status": "CREATED",
        })
        order_service.update(buy.id, {
            "status": OrderStatus.CLOSED.value,
            "filled": 0.01,
            "remaining": 0,
        })

        # Try to sell more than we have
        with self.assertRaises(Exception):
            order_service.create({
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 1.0,  # way more than 0.01
                "order_side": OrderSide.SELL.value,
                "price": 100,
                "order_type": OrderType.MARKET.value,
                "portfolio_id": 1,
                "status": "CREATED",
                "metadata": {"estimated_price": 100},
            })
