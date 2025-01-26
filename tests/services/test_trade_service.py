from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, TradeStatus
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

    def test_create_trade_from_buy_order(self):
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
        self.assertEqual(2004, trade.remaining)

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

    def test_update_trade(self):
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
        self.assertEqual(0, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
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
        self.assertEqual(1000, trade.amount)
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
        self.assertEqual(1000, trade.amount)
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

    def test_close_trades(self):
        portfolio = self.app.algorithm.get_portfolio()
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
        trade_service = self.app.container.trade_service()

        order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "portfolio_id": portfolio.id
        })

        # Update the buy order to closed
        order_service = self.app.container.order_service()
        order_service.update(
            order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )

        # Check that the trade was updated
        trade = trade_service.find(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )
        self.assertEqual(2004, trade.amount)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertEqual(1, len(trade.orders))

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
        trade_service = self.app.container.trade_service()
         # Check that the trade was updated
        trade = trade_service.find(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )
        self.assertEqual(2004, trade.amount)
        self.assertEqual(2004, trade.remaining)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        # Amount of orders should be 1, because the sell order has not
        # been filled
        self.assertEqual(1, len(trade.orders))

        # Update the sell order to closed
        order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
            "portfolio_id": portfolio.id
        })
        order_service.update(
            order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": 2004,
            }
        )

        trade_service = self.app.container.trade_service()
         # Check that the trade was updated
        trade = trade_service.find(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(0.2, trade.open_price)
        self.assertAlmostEqual(2004 * 0.3 - 2004 * 0.2, trade.net_gain)
        self.assertEqual(2, len(trade.orders))

    def test_close_trades_with_no_open_trades(self):
        portfolio = self.app.algorithm.get_portfolio()
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
        portfolio = self.app.algorithm.get_portfolio()
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

        order_service.create(
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


        # Update the sell order to closed
        order = order_service.find({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "order_side": "SELL",
            "portfolio_id": portfolio.id
        })
        order_service.update(
            order.id,
            {
                "status": OrderStatus.CLOSED.value,
                "filled": order.amount,
            }
        )

        trade_service = self.app.container.trade_service()
        self.assertEqual(2, len(trade_service.get_all()))
        trades = trade_service.get_all(
            {"target_symbol": "ADA", "trading_symbol": "EUR"}
        )

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
        portfolio = self.app.algorithm.get_portfolio()
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
        self.assertEqual(1000, trade.amount)
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
        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
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
        self.assertEqual(trade.status, "CLOSED")
        self.assertIsNotNone(trade.closed_at)
        self.assertIsNotNone(trade.net_gain)

    # def test_trade_closing_losing_trade(self):
    #     order_service = self.app.container.order_service()
    #     buy_order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 1000,
    #             "order_side": "BUY",
    #             "price": 0.2,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     updated_buy_order = order_service.update(
    #         buy_order.id,
    #         {
    #             "status": "CLOSED",
    #             "filled":  1000,
    #             "remaining": 0,
    #         }
    #     )
    #     self.assertEqual(updated_buy_order.amount, 1000)
    #     self.assertEqual(updated_buy_order.filled, 1000)
    #     self.assertEqual(updated_buy_order.remaining, 0)

    #     # Create a sell order with a higher price
    #     sell_order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 1000,
    #             "order_side": "SELL",
    #             "price": 0.1,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(0.1, sell_order.get_price())
    #     updated_sell_order = order_service.update(
    #         sell_order.id,
    #         {
    #             "status": "CLOSED",
    #             "filled": 1000,
    #             "remaining": 0,
    #         }
    #     )
    #     self.assertEqual(0.1, updated_sell_order.get_price())
    #     self.assertEqual(updated_sell_order.amount, 1000)
    #     self.assertEqual(updated_sell_order.filled, 1000)
    #     self.assertEqual(updated_sell_order.remaining, 0)
    #     buy_order = order_service.get(buy_order.id)
    #     self.assertEqual(buy_order.status, "CLOSED")
    #     self.assertIsNotNone(buy_order.get_trade_closed_at())
    #     self.assertIsNotNone(buy_order.get_trade_closed_price())
    #     self.assertEqual(-100, buy_order.get_net_gain())