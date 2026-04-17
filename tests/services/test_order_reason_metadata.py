"""
Tests for Order.metadata.order_reason on stop-loss and take-profit
sell order data dicts produced by TradeService.

Uses the same pattern as tests/services/test_trade_service.py with
storage_repo_type = "pandas".
"""
from datetime import datetime

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus
from tests.resources import TestBase


class TestStopLossOrderReasonMetadata(TestBase):
    """
    Verify that get_triggered_stop_loss_orders() includes
    metadata={"order_reason": "stop_loss"} in each returned data dict.
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

    def test_stop_loss_order_data_has_metadata(self):
        """
        1. Create filled buy order for ADA at 20 EUR
        2. Add stop loss at 10% (stop price = 18 EUR)
        3. Update last_reported_price to 17 (triggers SL)
        4. Check order data dict has metadata.order_reason == "stop_loss"
        """
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

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

        trade = trade_service.find({"order_id": buy_order.id})
        trade_service.add_stop_loss(
            trade, 10, False, sell_percentage=100
        )

        trade_service.update(
            trade.id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        order_service.check_pending_orders()
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(sell_order_data))

        data = sell_order_data[0]
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["order_reason"], "stop_loss")

    def test_multiple_stop_loss_orders_all_have_metadata(self):
        """Multiple triggered SL orders each have order_reason."""
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        # Trade 1: ADA
        buy_1 = order_service.create({
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
        trade_1 = trade_service.find({"order_id": buy_1.id})
        trade_service.add_stop_loss(
            trade_1, 10, False, sell_percentage=50
        )

        # Trade 2: DOT
        buy_2 = order_service.create({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "amount": 20,
            "filled": 20,
            "remaining": 0,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CLOSED",
        })
        trade_2 = trade_service.find({"order_id": buy_2.id})
        trade_service.add_stop_loss(
            trade_2, 10, True, sell_percentage=25
        )

        # Trigger both
        trade_service.update(trade_1.id, {
            "last_reported_price": 17,
            "last_reported_price_datetime": datetime.now(),
        })
        trade_service.update(trade_2.id, {
            "last_reported_price": 7,
            "last_reported_price_datetime": datetime.now(),
        })

        order_service.check_pending_orders()
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(2, len(sell_order_data))

        for data in sell_order_data:
            self.assertIn("metadata", data)
            self.assertEqual(
                data["metadata"]["order_reason"], "stop_loss"
            )


class TestTakeProfitOrderReasonMetadata(TestBase):
    """
    Verify that get_triggered_take_profit_orders() includes
    metadata={"order_reason": "take_profit"} in each returned data dict.
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

    def test_take_profit_order_data_has_metadata(self):
        """
        1. Create filled buy order for ADA at 20 EUR
        2. Add take profit at 10% (TP price = 22 EUR)
        3. Update last_reported_price to 23 (triggers TP)
        4. Check order data dict has metadata.order_reason == "take_profit"
        """
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

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

        trade = trade_service.find({"order_id": buy_order.id})
        trade_service.add_take_profit(
            trade, 10, False, sell_percentage=100
        )

        trade_service.update(
            trade.id,
            {
                "last_reported_price": 23,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        order_service.check_pending_orders()
        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(1, len(sell_order_data))

        data = sell_order_data[0]
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["order_reason"], "take_profit")

    def test_multiple_take_profit_orders_all_have_metadata(self):
        """Multiple triggered TP orders each have order_reason."""
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        # Trade 1: ADA
        buy_1 = order_service.create({
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
        trade_1 = trade_service.find({"order_id": buy_1.id})
        trade_service.add_take_profit(
            trade_1, 10, False, sell_percentage=50
        )

        # Trade 2: DOT
        buy_2 = order_service.create({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "amount": 20,
            "filled": 20,
            "remaining": 0,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CLOSED",
        })
        trade_2 = trade_service.find({"order_id": buy_2.id})
        trade_service.add_take_profit(
            trade_2, 10, False, sell_percentage=25
        )

        # Trigger both
        trade_service.update(trade_1.id, {
            "last_reported_price": 23,
            "last_reported_price_datetime": datetime.now(),
        })
        trade_service.update(trade_2.id, {
            "last_reported_price": 12,
            "last_reported_price_datetime": datetime.now(),
        })

        order_service.check_pending_orders()
        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(2, len(sell_order_data))

        for data in sell_order_data:
            self.assertIn("metadata", data)
            self.assertEqual(
                data["metadata"]["order_reason"], "take_profit"
            )
