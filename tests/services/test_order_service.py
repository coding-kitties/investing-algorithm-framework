import os
from decimal import Decimal

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration
from tests.resources import TestBase, MarketServiceStub


class TestOrderService(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="binance",
                api_key="test",
                secret_key="test",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.initialize()

    def test_create_limit_order(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "USDT",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(order.filled, None)
        self.assertEqual(order.remaining, 2004.5303357979318)

    def test_update_order(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "USDT",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        updated_order = order_service.update(
            order.id,
            {
                "status": "CLOSED",
                "filled": 2004.5303357979318,
                "remaining": Decimal('0'),
            }
        )
        self.assertEqual(updated_order.amount, 2004.5303357979318)
        self.assertEqual(updated_order.filled, 2004.5303357979318)
        self.assertEqual(updated_order.remaining, 0)

        position_service = self.app.container.position_service()
        position = position_service.get(order.position_id)
        self.assertEqual(position.amount, 2004.5303357979318)

    def test_create_limit_buy_order(self):
        pass

    def test_create_limit_sell_order(self):
        pass

    def test_update_buy_order_with_successful_order(self):
        pass

    def test_update_buy_order_with_successful_order_filled(self):
        pass

    def test_update_sell_order_with_successful_order(self):
        pass

    def test_update_sell_order_with_successful_order_filled(self):
        pass

    def test_update_buy_order_with_failed_order(self):
        pass

    def test_update_sell_order_with_failed_order(self):
        pass

    def test_update_buy_order_with_cancelled_order(self):
        pass

    def test_update_sell_order_with_cancelled_order(self):
        pass

    def test_trade_closing_winning_trade(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "USDT",
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
                "trading_symbol": "USDT",
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
        self.assertEqual(0.3, updated_sell_order.get_price())
        self.assertEqual(updated_sell_order.amount, 1000)
        self.assertEqual(updated_sell_order.filled, 1000)
        self.assertEqual(updated_sell_order.remaining, 0)
        buy_order = order_service.get(buy_order.id)
        self.assertEqual(buy_order.status, "CLOSED")
        self.assertIsNotNone(buy_order.get_trade_closed_at())
        self.assertIsNotNone(buy_order.get_trade_closed_price())
        self.assertNotEqual(0, buy_order.get_net_gain())

    def test_trade_closing_losing_trade(self):
        order_service = self.app.container.order_service()
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "USDT",
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
                "filled":  1000,
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
                "trading_symbol": "USDT",
                "amount": 1000,
                "order_side": "SELL",
                "price": 0.1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(0.1, sell_order.get_price())
        updated_sell_order = order_service.update(
            sell_order.id,
            {
                "status": "CLOSED",
                "filled": 1000,
                "remaining": 0,
            }
        )
        self.assertEqual(0.1, updated_sell_order.get_price())
        self.assertEqual(updated_sell_order.amount, 1000)
        self.assertEqual(updated_sell_order.filled, 1000)
        self.assertEqual(updated_sell_order.remaining, 0)
        buy_order = order_service.get(buy_order.id)
        self.assertEqual(buy_order.status, "CLOSED")
        self.assertIsNotNone(buy_order.get_trade_closed_at())
        self.assertIsNotNone(buy_order.get_trade_closed_price())
        self.assertEqual(-100, buy_order.get_net_gain())
