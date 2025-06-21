from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, TradeStatus
from tests.resources import TestBase


class TestOrderService(TestBase):
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
    external_balances = {
        "EUR": 1000
    }

    def test_create_limit_order(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
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
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

    def test_update_order(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
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
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
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
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

    def test_create_limit_sell_order(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
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
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

        order_service.update(
            order.id,
            {
                "status": "CLOSED",
                "filled": 2004.5303357979318,
                "remaining": Decimal('0'),
            }
        )

        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "SELL",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(2, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("SELL", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())

        # Because its synced
        self.assertEqual("OPEN", order.get_status())

    def test_update_buy_order_with_successful_order(self):
        pass

    def test_update_buy_order_with_successful_order_filled(self):
        pass

    def test_update_sell_order_with_successful_order(self):
        pass

    def test_update_sell_order_closing_partial_buy_orders(self):
        order_service = self.app.container.order_service()
        buy_order_one = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 5,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order_one.id,
            {
                "status": "CLOSED",
                "filled": 5,
                "remaining": Decimal('0'),
            }
        )
        buy_order_two = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 5,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            buy_order_two.id,
            {
                "status": "CLOSED",
                "filled": 5,
                "remaining": Decimal('0'),
            }
        )
        sell_order_one = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2.5,
                "order_side": "SELL",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            sell_order_one.id,
            {
                "status": "CLOSED",
                "filled": 2.5,
                "remaining": Decimal('0'),
            }
        )
        buy_order_one = order_service.get(buy_order_one.id)
        buy_order_two = order_service.get(buy_order_two.id)
        self.assertEqual(5, buy_order_one.get_filled())
        self.assertEqual(5, buy_order_two.get_filled())
        sell_order_two = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 5,
                "order_side": "SELL",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            sell_order_two.id,
            {
                "status": "CLOSED",
                "filled": 5,
                "remaining": Decimal('0'),
            }
        )
        buy_order_one = order_service.get(buy_order_one.id)
        buy_order_two = order_service.get(buy_order_two.id)
        self.assertEqual(5, buy_order_one.get_filled())
        self.assertEqual(5, buy_order_two.get_filled())

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

    def test_create_buy_order_with_order_amount_changed_by_market(self):
        """
        This test is to check if the order amount is changed by the market
        that the trade and position are also updated.

        For the trade object, the amount should be updated, and the remaining
        amount should be also updated.

        For the position object, the amount should be updated to the
        amount of the order and the cost should be updated.
        """
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount = 999
        order_executor.order_amount_filled = 999

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, order.get_remaining())
        self.assertEqual(999, order.get_filled())
        self.assertEqual(999, order.get_amount())

        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(999, position.amount)
        self.assertEqual(999, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )

        self.assertEqual(999, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(999, trade.filled_amount)
        self.assertEqual(999, trade.available_amount)
        self.assertEqual(1, trade.open_price)

    def test_update_buy_order_with_order_amount_changed_by_market(self):
        """
        This test is to check if the order amount is changed during updating
        by the market that the trade and position are also updated.

        For the trade object, the amount should be updated, and the remaining
        amount should be also updated.

        For the position object, the amount should be updated to the
        amount of the order and the cost should be updated.
        """
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(1000, order.get_remaining())
        self.assertEqual(0, order.get_filled())
        self.assertEqual(1000, order.get_amount())

        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(0, position.amount)
        self.assertEqual(0, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(1000, trade.remaining)
        self.assertEqual(0, trade.filled_amount)
        self.assertEqual(0, trade.available_amount)
        self.assertEqual(1, trade.open_price)

        portfolio_provider_lookup = self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance",
        )
        portfolio_provider = portfolio_provider_lookup.get_portfolio_provider(
            "binance"
        )
        portfolio_provider.order_amount = 999
        portfolio_provider.order_amount_filled = 999

        order_service.check_pending_orders()

        order = order_service.get(order.id)
        self.assertEqual(0, order.get_remaining())
        self.assertEqual(999, order.get_filled())
        self.assertEqual(999, order.get_amount())
        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(999, position.amount)
        self.assertEqual(999, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )
        self.assertEqual(999, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(999, trade.filled_amount)
        self.assertEqual(999, trade.available_amount)
        self.assertEqual(1, trade.open_price)

    def test_create_sell_order_with_order_amount_changed_by_market(self):
        """
        This test is to check if the order amount is changed by the market
        that the trade and position are also updated.

        For the trade object, the amount should be updated, and the remaining
        amount should be also updated.

        For the position object, the amount should be updated to the
        amount of the order and the cost should be updated.
        """
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 1000

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, order.get_remaining())
        self.assertEqual(1000, order.get_filled())
        self.assertEqual(1000, order.get_amount())

        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(1000, position.amount)
        self.assertEqual(1000, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1000, trade.available_amount)
        self.assertEqual(1, trade.open_price)

        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 999
        order_executor.order_amount = 999

        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "SELL",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, sell_order.get_remaining())
        self.assertEqual(999, sell_order.get_filled())
        self.assertEqual(999, sell_order.get_amount())
        position = self.app.container.position_service().get(
            sell_order.position_id
        )
        self.assertEqual(1, position.amount)
        self.assertEqual(1, position.cost)

        trade = trade_service.find(
            {
                "order_id": sell_order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1, trade.available_amount)

    def test_update_sell_order_with_order_amount_changed_by_market(self):
        """
        This test is to check if the order amount is changed by the market
        that the trade and position are also updated.

        For the trade object, the amount should be updated, and the remaining
        amount should be also updated.

        For the position object, the amount should be updated to the
        amount of the order and the cost should be updated.
        """
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 1000

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, order.get_remaining())
        self.assertEqual(1000, order.get_filled())
        self.assertEqual(1000, order.get_amount())

        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(1000, position.amount)
        self.assertEqual(1000, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1000, trade.available_amount)
        self.assertEqual(1, trade.open_price)

        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 0
        order_executor.status = OrderStatus.OPEN.value
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "SELL",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(1000, sell_order.get_remaining())
        self.assertEqual(0, sell_order.get_filled())
        self.assertEqual(1000, sell_order.get_amount())
        position = self.app.container.position_service().get(
            sell_order.position_id
        )
        self.assertEqual(0, position.amount)
        self.assertEqual(0, position.cost)

        trade = trade_service.find(
            {
                "order_id": sell_order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(0, trade.available_amount)

        portfolio_provider_lookup = self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance",
        )
        portfolio_provider = portfolio_provider_lookup.get_portfolio_provider(
            "binance"
        )
        portfolio_provider.order_amount = 999
        portfolio_provider.order_amount_filled = 999
        order_service.check_pending_orders()

        order = order_service.get(sell_order.id)
        self.assertEqual(0, order.get_remaining())
        self.assertEqual(999, order.get_filled())
        self.assertEqual(999, order.get_amount())

        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(1, position.amount)
        self.assertEqual(1, position.cost)

        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )

        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1, trade.available_amount)

    def test_create_buy_order_that_has_been_filled_immediately(self):
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 1000
        order_executor.order_status = OrderStatus.CLOSED.value
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, order.get_remaining())
        self.assertEqual(1000, order.get_filled())
        self.assertEqual(1000, order.get_amount())
        self.assertEqual(OrderStatus.CLOSED.value, order.get_status())

        # Check position
        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(1000, position.amount)
        self.assertEqual(1000, position.cost)

        # Check portfolio
        portfolio = self.app.container.portfolio_service().get(
            position.portfolio_id
        )
        self.assertEqual(0, portfolio.get_unallocated())

        # Check trade
        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )
        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1000, trade.available_amount)
        self.assertEqual(1, trade.open_price)
        self.assertTrue(TradeStatus.OPEN.equals(trade.status))

    def test_create_sell_order_that_has_been_filled_immediately(self):
        trade_service = self.app.container.trade_service()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market(
            "binance",
        )
        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 1000
        order_executor.order_status = OrderStatus.CLOSED.value

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        self.assertEqual(0, order.get_remaining())
        self.assertEqual(1000, order.get_filled())
        self.assertEqual(1000, order.get_amount())
        self.assertEqual(OrderStatus.CLOSED.value, order.get_status())

        # Check position
        position = self.app.container.position_service().get(
            order.position_id
        )
        self.assertEqual(1000, position.amount)
        self.assertEqual(1000, position.cost)

        # Check portfolio
        portfolio = self.app.container.portfolio_service().get(
            position.portfolio_id
        )
        self.assertEqual(0, portfolio.get_unallocated())

        # Check trade
        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )
        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(1000, trade.available_amount)
        self.assertEqual(1, trade.open_price)
        self.assertTrue(TradeStatus.OPEN.equals(trade.status))

        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "SELL",
                "price": 2,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        order_executor = order_executor_lookup.get_order_executor(
            "binance"
        )
        order_executor.order_amount_filled = 1000
        order_executor.order_status = OrderStatus.CLOSED.value

        self.assertEqual(0, sell_order.get_remaining())
        self.assertEqual(1000, sell_order.get_filled())
        self.assertEqual(1000, sell_order.get_amount())
        self.assertEqual(OrderStatus.CLOSED.value, sell_order.get_status())

        # Check position
        position = self.app.container.position_service().get(
            sell_order.position_id
        )
        self.assertEqual(0, position.amount)

        # Check portfolio
        portfolio = self.app.container.portfolio_service().get(
            position.portfolio_id
        )
        self.assertEqual(2000, portfolio.get_unallocated())

        # Check trade
        trade = trade_service.find(
            {
                "order_id": order.id,
            }
        )
        self.assertEqual(1000, trade.amount)
        self.assertEqual(0, trade.remaining)
        self.assertEqual(1000, trade.filled_amount)
        self.assertEqual(0, trade.available_amount)
        self.assertEqual(1, trade.open_price)
        self.assertTrue(TradeStatus.CLOSED.equals(trade.status))
