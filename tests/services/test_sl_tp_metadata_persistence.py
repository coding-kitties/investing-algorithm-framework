"""
End-to-end tests for order_reason metadata on stop-loss and take-profit
orders flowing through order_service.create() → DB → read back.

The tests at test_order_reason_metadata.py verify the data dict output.
These tests verify the metadata survives into the persisted SQLOrder in
the database after order_service.create() processes the dict.
"""
from datetime import datetime

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus
from investing_algorithm_framework.domain import OrderSide
from tests.resources import TestBase


class TestStopLossMetadataPersistence(TestBase):
    """
    Verify stop_loss order_reason metadata persists through
    get_triggered_stop_loss_orders() → order_service.create() → DB.
    """
    storage_repo_type = "pandas"
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
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_stop_loss_order_persists_with_metadata(self):
        """
        1. Create filled buy, add stop loss
        2. Trigger stop loss
        3. Get triggered SL order data (contains metadata)
        4. Pass to order_service.create()
        5. Verify the persisted order has metadata.order_reason == "stop_loss"
        """
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        # Create filled buy order
        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "filled": 20,
            "remaining": 0,
            "order_side": "BUY",
            "price": 20,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CLOSED",
        })

        # Add stop loss (10% threshold → triggers at 18 EUR)
        trade = trade_service.find({"order_id": buy_order.id})
        trade_service.add_stop_loss(
            trade, 10, False, sell_percentage=100
        )

        # Update price to trigger stop loss
        trade_service.update(trade.id, {
            "last_reported_price": 17,
            "last_reported_price_datetime": datetime.now(),
        })

        order_service.check_pending_orders()

        # Get triggered SL order data dicts
        sl_orders_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(sl_orders_data))

        # Verify the data dict has metadata
        data = sl_orders_data[0]
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["order_reason"], "stop_loss")

        # Create the order through order_service (full pipeline)
        sell_order = order_service.create(data)

        # Verify the persisted order has metadata
        self.assertIsNotNone(sell_order)
        self.assertEqual(
            sell_order.metadata.get("order_reason"), "stop_loss",
            "Stop loss sell order lost metadata after order_service.create()"
        )


class TestTakeProfitMetadataPersistence(TestBase):
    """
    Verify take_profit order_reason metadata persists through
    get_triggered_take_profit_orders() → order_service.create() → DB.
    """
    storage_repo_type = "pandas"
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
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_take_profit_order_persists_with_metadata(self):
        """
        1. Create filled buy, add take profit
        2. Trigger take profit
        3. Get triggered TP order data (contains metadata)
        4. Pass to order_service.create()
        5. Verify the persisted order has metadata.order_reason == "take_profit"
        """
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        # Create filled buy order
        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "filled": 20,
            "remaining": 0,
            "order_side": "BUY",
            "price": 20,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CLOSED",
        })

        # Add take profit (10% threshold → triggers at 22 EUR)
        trade = trade_service.find({"order_id": buy_order.id})
        trade_service.add_take_profit(
            trade, 10, False, sell_percentage=100
        )

        # Update price to trigger take profit
        trade_service.update(trade.id, {
            "last_reported_price": 23,
            "last_reported_price_datetime": datetime.now(),
        })

        order_service.check_pending_orders()

        # Get triggered TP order data dicts
        tp_orders_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(1, len(tp_orders_data))

        # Verify the data dict has metadata
        data = tp_orders_data[0]
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["order_reason"], "take_profit")

        # Create the order through order_service (full pipeline)
        sell_order = order_service.create(data)

        # Verify the persisted order has metadata
        self.assertIsNotNone(sell_order)
        self.assertEqual(
            sell_order.metadata.get("order_reason"), "take_profit",
            "Take profit sell order lost metadata after order_service.create()"
        )
