from datetime import datetime
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, TradeStatus, TradeRiskType
from tests.resources import TestBase


class TestTradeService(TestBase):
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
    external_balances = {
        "EUR": 1000
    }

    def test_create_trade_from_buy_order_with_created_status(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CREATED",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CREATED.value, trade.status)

    def test_create_trade_from_buy_order_with_open_status(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 1000,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": OrderStatus.OPEN.value,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(1000, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)

    def test_create_trade_from_buy_order_with_closed_status(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "OPEN",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)

    def test_create_trade_from_buy_order_with_rejected_status(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": OrderStatus.REJECTED.value,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertIsNone(trade)

    def test_create_trade_from_buy_order_with_rejected_buy_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "REJECTED",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertIsNone(trade)

    def test_create_trade_from_buy_order_with_canceled_buy_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CANCELED",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertIsNone(trade)

    def test_create_trade_from_buy_order_with_expired_buy_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "EXPIRED",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertIsNone(trade)

    def test_update_trade_with_filled_buy_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CREATED",
            }
        )
        order_id = buy_order.id
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertEqual(TradeStatus.CREATED.value, trade.status)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(0, trade.remaining)
        buy_order = order_repository.get(order_id)
        buy_order = order_repository.update(
            buy_order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )
        trade = trade_service.update_trade_with_buy_order(2004, buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)

    def test_update_trade_with_existing_buy_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 1000,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CREATED",
            }
        )
        order_id = buy_order.id
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(1000, trade.remaining)
        buy_order = order_repository.get(order_id)
        buy_order = order_repository.update(
            buy_order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )
        trade = trade_service.update_trade_with_buy_order(1004, buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(2004, trade.remaining)

    def test_update_trade_with_existing_buy_order_and_partily_closed(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 1000,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CREATED",
            }
        )
        order_id = buy_order.id
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNotNone(trade.opened_at)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(1000, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        buy_order = order_repository.get(order_id)
        buy_order = order_repository.update(
            buy_order.id,
            {
                "status": OrderStatus.OPEN.value,
                "filled": 500,
            }
        )
        trade = trade_service.update_trade_with_buy_order(500, buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(1500, trade.remaining)

    def test_close_trades(self):
        portfolio = self.app.context.get_portfolio()
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        order_id = order.id
        trade_service = self.app.container.trade_service()

        # Fill the buy order
        order_service.update(
            order_id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )

        # Check that the trade was updated
        trade = trade_service.find(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )
        trade_id = trade.id
        self.assertEqual(2004, trade.amount)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(1, len(trade.orders))

        # Create a sell order
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "SELL",
                "price": 0.3,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        sell_order_id = sell_order.id

         # Check that the trade was updated and that the trade has
         # nothing remaining
        trade = trade_service.get(trade_id)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(2, len(trade.orders))

        # Fill the sell order
        order_service.update(
            sell_order_id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )

        # Check that the trade was updated
        trade = trade_service.get(trade_id)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertAlmostEqual(2004 * 0.3 - 2004 * 0.2, trade.net_gain)
        self.assertEqual(2, len(trade.orders))

    def test_active_trade_after_canceling_close_trades(self):
        portfolio = self.app.context.get_portfolio()
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        order_id = order.id
        trade_service = self.app.container.trade_service()

        # Fill the buy order
        order_service.update(
            order_id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )

        # Check that the trade was updated
        trade = trade_service.find(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )
        trade_id = trade.id
        self.assertEqual(2004, trade.amount)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(1, len(trade.orders))

        # Create a sell order
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "SELL",
                "price": 0.3,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        sell_order_id = sell_order.id

         # Check that the trade was updated and that the trade has
         # nothing remaining
        trade = trade_service.get(trade_id)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(2, len(trade.orders))

        # Cancel the sell order
        order_service.update(
            sell_order_id,
            {
                "status": OrderStatus.CANCELED.value,
            }
        )

         # Check that the trade was updated
        trade = trade_service.get(trade_id)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertAlmostEqual(0, trade.net_gain)
        self.assertEqual(2, len(trade.orders))

    def test_close_trades_with_no_open_trades(self):
        portfolio = self.app.context.get_portfolio()
        order_service = self.app.container.order_service()
        order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )

        with self.assertRaises(Exception) as context:
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 2004,
                    "filled": 0,
                    "order_side": "SELL",
                    "price": 0.3,
                    "order_type": "LIMIT",
                    "status": "CREATED",
                    "portfolio_id": portfolio.id,
                }
            )

        self.assertIn(
            "Order amount 2004 is larger then amount of open position 0.0",
            str(context.exception)
        )

    def test_close_trades_with_multiple_trades(self):
        portfolio = self.app.context.get_portfolio()
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2000,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        order_one_id = buy_order.id
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.25,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        order_two_id = buy_order.id

        orders = order_service.get_all({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "portfolio_id": portfolio.id
        })

        # Update the buy order to closed
        order_service = self.app.container.order_service()

        for order in orders:
            order_service.update(
                order.id,
                {
                    "status": OrderStatus.CLOSED.value,
                    "filled": order.amount,
                }
            )

        # Check that the trade was updated
        trade_service = self.app.container.trade_service()
        self.assertEqual(2, len(trade_service.get_all()))
        trades = trade_service.get_all(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )

        for t in trades:
            self.assertNotEqual(0, t.amount)
            self.assertEqual(t.amount, t.remaining)
            self.assertEqual(TradeStatus.OPEN.value, t.status)
            self.assertEqual(1, len(t.orders))

        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 3000,
                "filled": 0,
                "order_side": "SELL",
                "price": 0.3,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        sell_order_id = sell_order.id
        trade_service = self.app.container.trade_service()
        self.assertEqual(2, len(trade_service.get_all()))
        trades = trade_service.get_all(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )

        for t in trades:
            self.assertNotEqual(0, t.amount)
            self.assertEqual(0, t.remaining)
            self.assertEqual(TradeStatus.CLOSED.value, t.status)
            self.assertEqual(2, len(t.orders))

        order_service.update(
            sell_order_id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": sell_order.amount,
            }
        )

        trade_service = self.app.container.trade_service()
        self.assertEqual(2, len(trade_service.get_all()))
        trades = trade_service.get_all(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )

        self.assertEqual(2, len(trades))

        for t in trades:
            self.assertNotEqual(0, t.amount)
            self.assertNotEqual(t.amount, t.remaining)
            self.assertEqual(TradeStatus.CLOSED.value, t.status)
            self.assertEqual(2, len(t.orders))
            self.assertEqual(0, t.remaining)

        trade = trade_service.find({"order_id": order_one_id})
        self.assertEqual(200, trade.net_gain)

        trade = trade_service.find({"order_id": order_two_id})
        self.assertEqual(50, trade.net_gain)

    def test_close_trades_with_partailly_filled_buy_order(self):
        portfolio = self.app.context.get_portfolio()
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2000,
                "filled": 0,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )
        order_id = order.id
        order_service.update(
            order.id,
            {
                "status": OrderStatus.OPEN.value,
                "filled": order.amount / 2,
            }
        )

        trade_service = self.app.container.trade_service()
        trade = trade_service.find(
            {"order_id": order_id}
        )
        self.assertEqual(2000, trade.amount)
        self.assertEqual(1000, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(1, len(trade.orders))
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "filled": 0,
                "order_side": "SELL",
                "price": 0.3,
                "order_type": "LIMIT",
                "status": "CREATED",
                "portfolio_id": portfolio.id,
            }
        )

        order_service.update(
            order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 1000,
            }
        )
        trade = trade_service.find({"order_id": order_id})
        self.assertEqual(2000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertAlmostEqual(1000 * 0.3 - 1000 * 0.2, trade.net_gain)
        self.assertEqual(2, len(trade.orders))

    def test_trade_closing_winning_trade(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        updated_buy_order = order_service.update(
            buy_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        self.assertEqual(updated_buy_order.amount, 1000)
        self.assertEqual(updated_buy_order.filled, 1000)
        self.assertEqual(updated_buy_order.remaining, 0)

        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.amount, 1000)
        self.assertEqual(trade.remaining, 1000)
        self.assertEqual(trade.open_price, 0.2)

        # Create a sell order with a higher price
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "SELL",
                "price": 0.3,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(0.3, sell_order.get_price())
        updated_sell_order = order_service.update(
            sell_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        updated_sell_order = order_service.get(sell_order.id)
        self.assertEqual(0.3, updated_sell_order.get_price())
        self.assertEqual(updated_sell_order.amount, 1000)
        self.assertEqual(updated_sell_order.filled, 1000)
        self.assertEqual(updated_sell_order.remaining, 0)

        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )

        self.assertEqual(100.0, trade.net_gain)
        self.assertEqual(trade.status, "CLOSED")
        self.assertIsNotNone(trade.closed_at)

    def test_add_stop_loss_to_trade(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )
        trade_service.add_stop_loss(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(1, len(trade.stop_losses))
        trade_service.add_stop_loss(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(2, len(trade.stop_losses))

    def test_add_stop_loss_to_trade_with_already_reached_sell_percentage(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )
        trade_service.add_stop_loss(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(1, len(trade.stop_losses))
        trade_service.add_stop_loss(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(2, len(trade.stop_losses))

        with self.assertRaises(Exception) as context:
            trade_service.add_stop_loss(
                trade,
                10,
                "fixed",
                sell_percentage=50,
            )

        self.assertEqual(
            "Combined sell percentages of stop losses belonging "
            "to trade exceeds 100.",
            str(context.exception)
        )
        self.assertEqual(2, len(trade.stop_losses))

    def test_add_take_profit_to_trade(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )
        trade_service.add_take_profit(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(1, len(trade.take_profits))
        trade_service.add_take_profit(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(2, len(trade.take_profits))

    def test_add_take_profit_to_trade_with_already_reached_percentage(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 0.2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        trade_service = self.app.container.trade_service()
        trade = self.app.container.trade_service().find(
            {"order_id": buy_order.id}
        )
        trade_service.add_take_profit(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(1, len(trade.take_profits))
        trade_service.add_take_profit(
            trade,
            10,
            "fixed",
            sell_percentage=50,
        )
        trade = trade_service.find(
            {"order_id": buy_order.id}
        )
        self.assertEqual(2, len(trade.take_profits))

        with self.assertRaises(Exception) as context:
            trade_service.add_take_profit(
                trade,
                10,
                "fixed",
                sell_percentage=50,
            )

        self.assertEqual(
            "Combined sell percentages of stop losses belonging "
            "to trade exceeds 100.",
            str(context.exception)
        )
        self.assertEqual(2, len(trade.take_profits))

    def test_get_triggered_stop_loss_orders(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct
        """
        order_service = self.app.container.order_service()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        stop_loss_two = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_two.stop_loss_price)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.stop_losses))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 20,
                "remaining": 0,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        stop_loss_two = trade_service.add_stop_loss(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(1, len(trade_two.stop_losses))
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 7,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(2, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(7, order_data["price"])
                self.assertEqual(5, order_data["amount"])

            else:
                self.assertEqual(17, order_data["price"])
                self.assertEqual(15, order_data["amount"])

    def test_get_triggered_stop_loss_orders_with_unfilled_order(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR. This is order does not get filled.
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct. Only 1
            order should be created for ADA, given that the dot order was
            not filled.
        """
        order_service = self.app.container.order_service()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        stop_loss_two = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_two.stop_loss_price)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.stop_losses))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 0,
                "remaining": 20,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        stop_loss_two = trade_service.add_stop_loss(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(1, len(trade_two.stop_losses))
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 7,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(17, order_data["price"])
            self.assertEqual(15, order_data["amount"])

    def test_get_triggered_stop_loss_orders_with_cancelled_order(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct
        9. Cancel the the dot order
        10. Cancel the ada order after partially filling it with amount 5
        11. Check that the stop losses are active again and partially filled
             or entirely filled back.
        """
        order_service = self.app.container.order_service()
        buy_order_one = order_service.create(
            {
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
            }
        )

        # Check that the position costs are correctly updated
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": 1}
        )
        # 20 * 20 = 400
        self.assertEqual(400, ada_position.cost)

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        stop_loss_two = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_two.stop_loss_price)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.stop_losses))

        buy_order_two = order_service.create(
            {
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
            }
        )

        dot_position = self.app.container.position_service().find(
            {"symbol": "DOT", "portfolio_id": 1}
        )
        # 20 * 10 = 200
        self.assertEqual(200, dot_position.cost)

        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        stop_loss_two = trade_service.add_stop_loss(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(1, len(trade_two.stop_losses))
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 7,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(2, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(7, order_data["price"])
                self.assertEqual(5, order_data["amount"])

            else:
                self.assertEqual(17, order_data["price"])
                self.assertEqual(15, order_data["amount"])

        for order_data in sell_order_data:
            order_service.create(order_data)

        ada_sell_order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        dot_sell_order = order_service.find({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        dot_trade = trade_service.find(
            {"order_id": buy_order_two.id}
        )
        ada_trade = trade_service.find(
            {"order_id": buy_order_one.id}
        )

        self.assertEqual(2, len(ada_trade.orders))
        self.assertEqual(5, ada_trade.remaining)
        self.assertEqual(20, ada_trade.amount)

        self.assertEqual(2, len(dot_trade.orders))
        self.assertEqual(15, dot_trade.remaining)
        self.assertEqual(20, dot_trade.amount)

        # Update the ada order to be partially filled
        order_service.update(
            object_id=ada_sell_order.id,
            data={
                "filled": 5,
                "remaining": 10,
                "status": OrderStatus.CANCELED.value,
            }
        )

        # Cancel the dot order
        order_service.update(
            object_id=dot_sell_order.id,
            data={
                "status": OrderStatus.CANCELED.value,
            }
        )

        # Check that the positions are correctly updated with amount and cost
        dot_position = self.app.container.position_service().find(
            {"symbol": "DOT", "portfolio_id": 1}
        )
        # Position cost should be 200, since the order was not filled
        self.assertEqual(200, dot_position.cost)
        self.assertEqual(20, dot_position.amount)

        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": 1}
        )
        # Position cost should be 300, since the order was partially filled
        # with amount 5, 20 * 15 = 300
        self.assertEqual(15, ada_position.amount)
        self.assertEqual(300, ada_position.cost)

        # Check that the dot trade is open, with amount of 20, and net gain
        # of 0, and remaining of 20
        dot_trade = trade_service.find(
            {"order_id": buy_order_two.id}
        )
        self.assertEqual(2, len(ada_trade.orders))
        self.assertEqual(20, dot_trade.amount)
        self.assertEqual(0, dot_trade.net_gain)
        self.assertEqual(20, dot_trade.remaining)

        ada_trade = trade_service.find(
            {"order_id": buy_order_one.id}
        )
        # Check that the ada trade is open, with amount of 15, and net gain
        # of 5
        self.assertEqual(2, len(ada_trade.orders))
        self.assertEqual(15, ada_trade.remaining)
        self.assertEqual(20, ada_trade.amount)

        # Check that all stop losses are active again and filled back to
        # correct amount
        stop_losses = ada_trade.stop_losses

        for stop_loss in stop_losses:
            self.assertTrue(stop_loss.active)

            if stop_loss.trade_risk_type == "FIXED":
                self.assertEqual(10, stop_loss.sell_amount)
                self.assertEqual(5, stop_loss.sold_amount)
            else:
                self.assertEqual(5, stop_loss.sell_amount)
                self.assertEqual(0, stop_loss.sold_amount)

        stop_losses = dot_trade.stop_losses

        for stop_loss in stop_losses:
            self.assertTrue(stop_loss.active)
            self.assertEqual(5, stop_loss.sell_amount)
            self.assertEqual(0, stop_loss.sold_amount)

    def test_get_triggered_stop_loss_orders_with_partially_filled_orders(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Fill the ada order with amount 10
        7. Fill the dot order with amount 20
        8. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        9. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        10. Check that the triggered stop loss orders are correct
        # 9. Cancel the the dot order
        # 10. Cancel the ada order after partially filling it with amount 5
        # 11. Check that the stop losses are active again and partially filled
        #      or entirely filled back.
        """
        order_service = self.app.container.order_service()
        buy_order_one = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 10,
                "remaining": 0,
                "order_side": "BUY",
                "price": 20,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "OPEN",
            }
        )

        # Check that the position costs are correctly updated
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": 1}
        )
        # 10 * 20 = 200
        self.assertEqual(200, ada_position.cost)

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        stop_loss_two = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_two.stop_loss_price)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.stop_losses))

        buy_order_two = order_service.create(
            {
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
            }
        )

        dot_position = self.app.container.position_service().find(
            {"symbol": "DOT", "portfolio_id": 1}
        )
        # 20 * 10 = 200
        self.assertEqual(200, dot_position.cost)

        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        stop_loss_two = trade_service.add_stop_loss(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(1, len(trade_two.stop_losses))
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 7,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(2, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(7, order_data["price"])
                self.assertEqual(5, order_data["amount"])
            else:
                self.assertEqual(17, order_data["price"])
                self.assertEqual(10, order_data["amount"])

        for order_data in sell_order_data:
            order_service.create(order_data)

        ada_sell_order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        dot_sell_order = order_service.find({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        dot_trade = trade_service.find(
            {"order_id": buy_order_two.id}
        )
        ada_trade = trade_service.find(
            {"order_id": buy_order_one.id}
        )

        self.assertEqual(2, len(ada_trade.orders))
        self.assertEqual(0, ada_trade.remaining)
        self.assertEqual(20, ada_trade.amount)
        self.assertEqual("OPEN", ada_trade.status)

        self.assertEqual(2, len(dot_trade.orders))
        self.assertEqual(15, dot_trade.remaining)
        self.assertEqual(20, dot_trade.amount)

    def test_get_triggered_take_profits_orders(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a take profit with a trailing percentage of 10 and
            sell percentage 25 for the trade.

            The first take profit will trigger at 22 EUR, and the second
            take profit will set its high water mark and take profit price at 22 EUR, and only trigger if the price goes down from take profit price.

        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct
        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        take_profit_two = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.take_profits))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 20,
                "remaining": 0,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        take_profit_three = trade_service.add_take_profit(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(11, take_profit_three.take_profit_price)
        self.assertEqual(1, len(trade_two.take_profits))

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 11,            "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_take_profit_orders()

        # Only the ada order should be triggered, because its fixed
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(22, order_data["price"])
            self.assertEqual(10, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 25,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 14,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        # Take profit 2
        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(0, take_profit_two.sold_amount)

        # Take profit 3
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )

        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(0, take_profit_three.sold_amount)

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22.4,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 12.5,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(2, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(12.5, order_data["price"])
                self.assertEqual(5, order_data["amount"])

            else:
                self.assertEqual(22.4, order_data["price"])
                self.assertEqual(5, order_data["amount"])

    def test_get_triggered_take_profits_with_unfilled_order(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR. This is order does not get filled.
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct. Only 1
            order should be created for ADA, given that the dot order was
            not filled.
        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 10,
                "remaining": 10,
                "order_side": "BUY",
                "price": 20,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "OPEN",
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        self.assertEqual(10, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        take_profit_two = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.take_profits))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 20,
                "remaining": 0,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        take_profit_three = trade_service.add_take_profit(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(11, take_profit_three.take_profit_price)
        self.assertEqual(1, len(trade_two.take_profits))

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 11,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_take_profit_orders()

        # Only the ada order should be triggered, because its fixed
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(22, order_data["price"])
            self.assertEqual(10, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])

        # Execute the sell orders
        for data in sell_order_data:
            order_service.create(data)

        # Take profit 2
        take_profit_one = trade_take_profit_repository.get(
            take_profit_one.id
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        self.assertEqual(22, take_profit_one.high_water_mark)
        self.assertEqual(10, take_profit_one.sold_amount)

        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        self.assertEqual(0, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 25,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 14,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        # Take profit 2
        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(0, take_profit_two.sold_amount)

        # Take profit 3
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )

        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(0, take_profit_three.sold_amount)

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22.4,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 12.5,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        # Only one, because ada trade has nothing remaining
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(12.5, order_data["price"])
                self.assertEqual(5, order_data["amount"])

    def test_get_triggered_take_profits_orders_with_cancelled_order(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR (filled)
        2. Create a take profit with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a take profit price
            of 22 EUR
        3. Create a take profit with trailing percentage of 10 and
            sell percentage 25 for the trade.
        4. Create a buy order for DOT with amount 20 at 10 EUR (filled)
        5. Create a trailing take profit with percentage of 10 and
            sell percentage 25 for the trade. This is a take profit price
            initially set at 11 EUR
        6. Update the last reported price of ada to 22 EUR, triggering 1
            stop loss orders
        7. Update the last reported price of dot to 14 EUR, triggering 0
            stop loss order
        8. Check the stop loss orders are correct
        9. Update the last reported price of ada to 25 EUR, triggering 0
            stop loss orders
        10. Update the last reported price of dot to 14 EUR, triggering 0
            stop loss order
        11. Check the stop loss orders are correct (0 orders)
        12. Update the last reported price of ada to 22.4 EUR, triggering 1
            stop loss orders
        13. Update the last reported price of dot to 12.5 EUR, triggering 1
            stop loss order
        14. Check the stop loss orders are correct
        15. Fill the ada order with amount 2.5
        16. Cancel the dot order and ada order
        17. Check that the stop losses are active again and partially filled
        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        take_profit_two = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.take_profits))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 20,
                "remaining": 0,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        take_profit_three = trade_service.add_take_profit(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(11, take_profit_three.take_profit_price)
        self.assertEqual(1, len(trade_two.take_profits))

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 11,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_take_profit_orders()

        # Only the ada order should be triggered, because its fixed
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(22, order_data["price"])
            self.assertEqual(10, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])

        order = order_service.create(sell_order_data[0])
        order_service.update(
            order.id,
            {
                "filled": 10,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = trade_service.get(trade_one_id)
        trade_two = trade_service.get(trade_two_id)

        self.assertEqual(10, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        self.assertEqual(20, trade_two.remaining)
        self.assertEqual(20, trade_two.amount)
        self.assertEqual("OPEN", trade_two.status)

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 25,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 14,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        # Take profit 2
        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(0, take_profit_two.sold_amount)

        # Take profit 3
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )

        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(0, take_profit_three.sold_amount)

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22.4,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 12.5,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(2, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])

            if "DOT" == order_data["target_symbol"]:
                self.assertEqual(12.5, order_data["price"])
                self.assertEqual(5, order_data["amount"])

            else:
                self.assertEqual(22.4, order_data["price"])
                self.assertEqual(5, order_data["amount"])

        for order_data in sell_order_data:
            order_service.create(order_data)

        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(5, take_profit_two.sold_amount)

        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(5, take_profit_three.sold_amount)

        trade_service = self.app.container.trade_service()
        trade_one = trade_service.get(trade_one_id)
        trade_two = trade_service.get(trade_two_id)

        self.assertEqual(5, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        self.assertEqual(15, trade_two.remaining)
        self.assertEqual(20, trade_two.amount)
        self.assertEqual("OPEN", trade_two.status)

        # Fill the ada sell order with amount 2.5
        ada_sell_order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })
        order_service.update(
            ada_sell_order.id,
            {
                "filled": 2.5,
                "remaining": 2.5,
                "status": OrderStatus.OPEN.value,
            }
        )

        # Cancel the dot order
        dot_order = order_service.find({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        order_service.update(
            dot_order.id,
            {
                "status": OrderStatus.CANCELED.value,
            }
        )

        # Cancel the ada order
        ada_sell_order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
        })

        order_service.update(
            ada_sell_order.id,
            {
                "status": OrderStatus.CANCELED.value,
            }
        )

        trade_one = trade_service.get(trade_one_id)
        trade_two = trade_service.get(trade_two_id)

        self.assertEqual(7.5, trade_one.remaining)
        self.assertEqual("ADA", trade_one.target_symbol)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        self.assertEqual("DOT", trade_two.target_symbol)
        self.assertEqual(20, trade_two.remaining)
        self.assertEqual(20, trade_two.amount)
        self.assertEqual("OPEN", trade_two.status)

        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(2.5, take_profit_two.sold_amount)

        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(0, take_profit_three.sold_amount)

        ada_trade = trade_service.find(
            {"order_id": buy_order_one.id}
        )
        dot_trade = trade_service.find(
            {"order_id": buy_order_two.id}
        )
        dot_position = self.app.container.position_service().find(
            {"symbol": "DOT", "portfolio_id": 1}
        )

        # 20 * 10 = 200
        self.assertEqual(200, dot_position.cost)

        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": 1}
        )
        # 20 * 7.5 = 150
        self.assertEqual(150, ada_position.cost)

        # Check net gain, trade two should have a net gain of 5
        # Dot trade net gain should be 0
        self.assertEqual(0, dot_trade.net_gain)

        # Ada trade net gain should be:
        # First trade (10 * 22) - (10 * 20) = 20
        # Second trade (2.5 * 22.4) - (2.5 * 20) = 6
        # Total = 26
        self.assertEqual(26, ada_trade.net_gain)

    def test_get_triggered_tp_orders_with_partially_filled_orders(self):
        """
        Test for triggered take profit orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a tp with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a tp price
            of 22 EUR
        3. Create a tp with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a tp price
            that will be active at 22
        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing tp with percentage of 10 and
            sell percentage 25 for the trade. This is a tp price
            that will be active at 11 EUR
        6. Fill the ada order with amount 10
        7. Fill the dot order with amount 20
        8. Update the last reported price of ada to 22 EUR, triggering 1
            tp orders
        9. Update the last reported price of dot to 11 EUR, triggering 0
            tp order
        10. Check that the triggered tp orders are correct
        11. Fill the ada sell order with amount 10
        12. Update the last reported price of ada to 25 EUR, triggering 0
            tp orders
        13. Update the last reported price of ada to 22 EUR, triggering 1
            tp orders
        14. Check that no tp orders are triggered, because there is no amount
        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 10,
                "remaining": 0,
                "order_side": "BUY",
                "price": 20,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CLOSED",
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=50,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        take_profit_two = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(2, len(trade_one.take_profits))

        buy_order_two = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 20,
                "filled": 20,
                "remaining": 0,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        trade_two = self.app.container.trade_service().find(
            {"order_id": buy_order_two.id}
        )
        trade_two_id = trade_two.id
        take_profit_three = trade_service.add_take_profit(
            trade_two,
            10,
            "trailing",
            sell_percentage=25,
        )
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )
        trade_two = trade_service.get(trade_two_id)
        self.assertEqual(11, take_profit_three.take_profit_price)
        self.assertEqual(1, len(trade_two.take_profits))

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 11,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_take_profit_orders()

        # Only the ada order should be triggered, because its fixed
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(22, order_data["price"])
            self.assertEqual(10, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])

        order = order_service.create(sell_order_data[0])
        order_service.update(
            order.id,
            {
                "filled": 10,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = trade_service.get(trade_one_id)
        trade_two = trade_service.get(trade_two_id)

        self.assertEqual(0, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("OPEN", trade_one.status)

        self.assertEqual(20, trade_two.remaining)
        self.assertEqual(20, trade_two.amount)
        self.assertEqual("OPEN", trade_two.status)

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 25,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        trade_two = trade_service.update(
            trade_two_id,
            {
                "last_reported_price": 14,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        # Take profit 2
        take_profit_two = trade_take_profit_repository.get(
            take_profit_two.id
        )
        self.assertEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
        self.assertEqual(0, take_profit_two.sold_amount)

        # Take profit 3
        take_profit_three = trade_take_profit_repository.get(
            take_profit_three.id
        )

        self.assertEqual(12.6, take_profit_three.take_profit_price)
        self.assertEqual(14, take_profit_three.high_water_mark)
        self.assertEqual(0, take_profit_three.sold_amount)

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

        trade_one = trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22.4,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(0, len(sell_order_data))

    def test_deactivation_of_take_profits_when_stop_losses_are_triggered(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a take profit with a trailing percentage of 10 and
            sell percentage 25 for the trade.

            The first take profit will trigger at 22 EUR, and the second
            take profit will set its high water mark and take profit price at 22 EUR, and only trigger if the price goes down from take profit price.

        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct

        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=100,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )

        # Update the last reported price of ada to 17 EUR, triggering 1
        # stop loss order
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 17,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(17, order_data["price"])
            self.assertEqual(20, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])
            sell_order = order_service.create(order_data)

        # Trade should be closed
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(0, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("CLOSED", trade_one.status)

        # All stop losses should be deactivated
        for stop_loss in trade_one.stop_losses:
            self.assertFalse(stop_loss.active)

        # All take profits should be deactivated
        for take_profit in trade_one.take_profits:
            self.assertFalse(take_profit.active)

    def test_deactivation_of_stop_losses_when_take_profits_are_triggered(self):
        """
        Test for triggered stop loss orders:

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 50 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a take profit with a trailing percentage of 10 and
            sell percentage 25 for the trade.

            The first take profit will trigger at 22 EUR, and the second
            take profit will set its high water mark and take profit price at 22 EUR, and only trigger if the price goes down from take profit price.

        4. Create a buy order for DOT with amount 20 at 10 EUR
        5. Create a trailing stop loss with percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 7 EUR
        6. Update the last reported price of ada to 17 EUR, triggering 2
            stop loss orders
        7. Update the last reported price of dot to 7 EUR, triggering 1
            stop loss order
        8. Check that the triggered stop loss orders are correct

        """
        order_service = self.app.container.order_service()
        trade_take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=100,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )

        # Update the last reported price of ada to 17 EUR, triggering 1
        # stop loss order
        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )
        sell_order_data = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(1, len(sell_order_data))

        for order_data in sell_order_data:
            self.assertEqual("SELL", order_data["order_side"])
            self.assertEqual("EUR", order_data["trading_symbol"])
            self.assertEqual(1, order_data["portfolio_id"])
            self.assertEqual("LIMIT", order_data["order_type"])
            self.assertEqual(22, order_data["price"])
            self.assertEqual(20, order_data["amount"])
            self.assertEqual("ADA", order_data["target_symbol"])
            sell_order = order_service.create(order_data)

        # Trade should be closed
        trade_one = trade_service.get(trade_one_id)
        self.assertEqual(0, trade_one.remaining)
        self.assertEqual(20, trade_one.amount)
        self.assertEqual("CLOSED", trade_one.status)

        # All stop losses should be deactivated
        for stop_loss in trade_one.stop_losses:
            self.assertFalse(stop_loss.active)

        # All take profits should be deactivated
        for take_profit in trade_one.take_profits:
            self.assertFalse(take_profit.active)

    def test_update_stop_losses_trailing_price_increase(self):
        """
        Test if the stop losses are triggered correctly when the last reported
        price is updated. This test will check for both fixed and trailing
        stop losses if they are triggered correctly and also if the high water
        mark is updated correctly.

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 10 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Update the last reported price of ada to 21 EUR, triggering 0
            stop loss orders. The trailing stop loss should be updated to
            19.8 EUR. Both stop losses should have their high water mark
            set to 21 EUR
        5. Update the last reported price of ada to 22 EUR. The trailing
            stop loss should be updated to 20 EUR, and the fixed stop loss
            should not be triggered. Both stop losses should have their
            high water mark set to 22 EUR.
        """
        order_service = self.app.container.order_service()
        stop_loss_repository = self.app.container.\
            trade_stop_loss_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        stop_loss_one = trade_service.add_stop_loss(
            trade_one,
            10,
            "fixed",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)

        # Create a stop loss with a trailing percentage of 10 and
        # sell percentage 25 for the trade.
        stop_loss_two = trade_service.add_stop_loss(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(18, stop_loss_two.stop_loss_price)
        self.assertEqual(20, stop_loss_two.high_water_mark)

        # Update the last reported price of ada to 21 EUR, triggering 0
        # stop loss orders. The trailing stop loss should be updated to
        # 18.9. Both stop losses should have their high water mark
        # set to 21 EUR

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 21,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        stop_loss_one = stop_loss_repository.get(
            stop_loss_one.id
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        self.assertEqual(21, stop_loss_one.high_water_mark)

        stop_loss_two = stop_loss_repository.get(
            stop_loss_two.id
        )
        self.assertAlmostEqual(18.9, stop_loss_two.stop_loss_price)
        self.assertEqual(21, stop_loss_two.high_water_mark)

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 22,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        stop_loss_one = stop_loss_repository.get(
            stop_loss_one.id
        )
        self.assertEqual(18, stop_loss_one.stop_loss_price)
        self.assertEqual(22, stop_loss_one.high_water_mark)

        stop_loss_two = stop_loss_repository.get(
            stop_loss_two.id
        )
        self.assertAlmostEqual(19.8, stop_loss_two.stop_loss_price)
        self.assertEqual(22, stop_loss_two.high_water_mark)

    def test_update_latest_price_and_take_profits(self):
        """
        Test if the stop losses are triggered correctly when the last reported
        price is updated. This test will check for both fixed and trailing
        stop losses if they are triggered correctly and also if the high water
        mark is updated correctly.

        1. Create a buy order for ADA with amount 20 at 20 EUR
        2. Create a stop loss with fixed percentage of 10 and
            sell percentage 10 for the trade. This is a stop loss price
            of 18 EUR
        3. Create a stop loss with trailing percentage of 10 and
            sell percentage 25 for the trade. This is a stop loss price
            initially set at 18 EUR
        4. Update the last reported price of ada to 21 EUR, triggering 0
            stop loss orders. The trailing stop loss should be updated to
            19.8 EUR. Both stop losses should have their high water mark
            set to 21 EUR
        5. Update the last reported price of ada to 22 EUR. The trailing
            stop loss should be updated to 20 EUR, and the fixed stop loss
            should not be triggered. Both stop losses should have their
            high water mark set to 22 EUR.
        """
        order_service = self.app.container.order_service()
        take_profit_repository = self.app.container.\
            trade_take_profit_repository()
        buy_order_one = order_service.create(
            {
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
            }
        )

        trade_service = self.app.container.trade_service()
        trade_one = self.app.container.trade_service().find(
            {"order_id": buy_order_one.id}
        )
        trade_one_id = trade_one.id
        take_profit_one = trade_service.add_take_profit(
            trade_one,
            10,
            "fixed",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_one.take_profit_price)

        # Create a stop loss with a trailing percentage of 10 and
        # sell percentage 25 for the trade.
        take_profit_two = trade_service.add_take_profit(
            trade_one,
            10,
            "trailing",
            sell_percentage=25,
        )
        self.assertEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)

        # Update the last reported price of ada to 21 EUR, triggering 0
        # stop loss orders. The trailing stop loss should be updated to
        # 18.9. Both stop losses should have their high water mark
        # set to 21 EUR

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 21,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        take_profit_one = take_profit_repository.get(
            take_profit_one.id
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        self.assertEqual(None, take_profit_one.high_water_mark)

        take_profit_two = take_profit_repository.get(
            take_profit_two.id
        )

        self.assertAlmostEqual(22, take_profit_two.take_profit_price)
        self.assertEqual(None, take_profit_two.high_water_mark)

        trade_service.update(
            trade_one_id,
            {
                "last_reported_price": 25,
                "last_reported_price_datetime": datetime.now(),
            }
        )

        take_profit_one = take_profit_repository.get(
            take_profit_one.id
        )
        self.assertEqual(22, take_profit_one.take_profit_price)
        self.assertEqual(25, take_profit_one.high_water_mark)

        take_profit_two = take_profit_repository.get(
            take_profit_two.id
        )
        self.assertAlmostEqual(22.5, take_profit_two.take_profit_price)
        self.assertEqual(25, take_profit_two.high_water_mark)
