"""
Tests for order_reason metadata in the production (live) order path.

Verifies that metadata passed through create_limit_order() in
non-backtest mode survives the full pipeline:
  context.create_limit_order(metadata=...) → order_service.create()
  → SQLOrder(**data) → DB → repository.get() → metadata intact
"""
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus
from investing_algorithm_framework.domain import OrderSide
from tests.resources import TestBase


class TestProductionOrderMetadata(TestBase):
    """
    Tests for metadata persistence in the production (non-backtest) path.
    Uses TestBase which sets up a full app with DB, order executor, etc.
    """
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def test_create_limit_buy_order_with_metadata(self):
        """
        Production path: create_limit_order with metadata → DB → read back.
        """
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
            metadata={"order_reason": "buy_signal"},
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertIsNotNone(order)
        self.assertEqual(
            order.metadata.get("order_reason"), "buy_signal"
        )

    def test_create_limit_sell_order_with_metadata(self):
        """
        Production path: sell order with sell_signal metadata persisted.
        Uses order_service.create() which is how SL/TP orders are created.
        """
        order_service = self.app.container.order_service()
        # Create a filled buy first to establish position
        buy_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 10,
            "filled": 10,
            "remaining": 0,
            "price": 10,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CLOSED",
        })
        order_service.check_pending_orders()
        # Now create sell
        sell_order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 1,
            "price": 10,
            "order_side": "SELL",
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "OPEN",
            "metadata": {"order_reason": "sell_signal"},
        })
        self.assertEqual(
            sell_order.metadata.get("order_reason"), "sell_signal"
        )

    def test_create_order_without_metadata_returns_empty_dict(self):
        """
        Production path: order without metadata has empty dict.
        """
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(order.metadata, {})

    def test_metadata_with_custom_fields_persists(self):
        """
        Production path: arbitrary metadata dict persists through DB.
        """
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
            metadata={
                "order_reason": "scale_in",
                "scale_in_index": 2,
                "strategy_id": "momentum_v3",
            },
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(order.metadata["order_reason"], "scale_in")
        self.assertEqual(order.metadata["scale_in_index"], 2)
        self.assertEqual(order.metadata["strategy_id"], "momentum_v3")
