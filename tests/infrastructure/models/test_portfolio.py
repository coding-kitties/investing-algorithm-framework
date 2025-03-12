from investing_algorithm_framework.infrastructure import SQLPortfolio
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase


class TestPortfolioModel(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="USDT"
        )
    ]
    external_balances = {
        "USDT": 10000
    }
    market_credentials = [
        MarketCredential(
            market="BINANCE",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]

    def test_default(self):
        portfolio = SQLPortfolio(
            trading_symbol="USDT",
            market="BINANCE",
            unallocated=10000,
            initialized=True
        )
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("USDT", portfolio.get_trading_symbol())
        self.assertEqual(10000, portfolio.get_unallocated())
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("BINANCE", portfolio.get_identifier())
        self.assertEqual(0, portfolio.get_realized())
        self.assertEqual(0, portfolio.get_total_revenue())
        self.assertEqual(0, portfolio.get_total_cost())
        self.assertEqual(0, portfolio.get_total_net_gain())
        self.assertEqual(0, portfolio.get_total_trade_volume())
        self.assertEqual(10000, portfolio.get_net_size())
        self.assertIsNone(portfolio.get_initial_balance())
        self.assertIsNotNone(portfolio.get_created_at())
        self.assertIsNone(portfolio.get_updated_at())

    def test_created_by_app(self):
        portfolio = self.app.context.get_portfolio()
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("USDT", portfolio.get_trading_symbol())
        self.assertEqual(10000, portfolio.get_unallocated())
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("BINANCE", portfolio.get_identifier())
        self.assertEqual(0, portfolio.get_realized())
        self.assertEqual(0, portfolio.get_total_revenue())
        self.assertEqual(0, portfolio.get_total_cost())
        self.assertEqual(0, portfolio.get_total_net_gain())
        self.assertEqual(0, portfolio.get_total_trade_volume())
        self.assertEqual(10000, portfolio.get_net_size())
        self.assertIsNone(portfolio.get_initial_balance())
        self.assertIsNotNone(portfolio.get_created_at())
        self.assertIsNotNone(portfolio.get_updated_at())

    # def test_get_trading_symbol(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     self.assertIsNotNone(portfolio.get_trading_symbol())

    # def test_get_unallocated(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     self.create_buy_order(
    #         amount=1,
    #         target_symbol=self.TARGET_SYMBOL_A,
    #         portfolio_manager=portfolio_manager,
    #         reference_id=10,
    #         price=10
    #     )

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)

    #     self.assertIsNotNone(portfolio.get_unallocated())
    #     self.assertIsNotNone(portfolio.get_unallocated())
    #     self.assertTrue(
    #         isinstance(portfolio.get_unallocated(), Position)
    #     )

    # def test_get_allocated(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     self.create_buy_order(
    #         amount=1,
    #         target_symbol=self.TARGET_SYMBOL_A,
    #         portfolio_manager=portfolio_manager,
    #         reference_id=10,
    #         price=10
    #     )

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     positions = portfolio.get_positions()

    #     for position in positions:
    #         position.price = self.get_price(position.get_symbol()).price

    #     self.assertIsNotNone(portfolio.get_allocated())
    #     self.assertNotEqual(0, portfolio.get_allocated())

    # def test_get_id(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     self.assertIsNotNone(portfolio.get_identifier())

    # def test_get_total_revenue(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     self.assertIsNotNone(portfolio.get_total_revenue())
    #     self.assertEqual(0, portfolio.get_total_revenue())

    # def test_add_order(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     order = portfolio_manager.create_order(
    #         amount=10,
    #         target_symbol=self.TARGET_SYMBOL_A,
    #         price=self.get_price(self.TARGET_SYMBOL_A).price,
    #         order_type=OrderType.LIMIT.value
    #     )

    #     order.status = OrderStatus.PENDING
    #     order.reference_id = 2
    #     db.session.commit()
    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)

    #     self.assertEqual(0, len(portfolio.get_orders()))
    #     self.assertEqual(1, len(portfolio.get_positions()))

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_order(order)

    #     self.assertEqual(1, len(portfolio.get_orders()))
    #     self.assertEqual(2, len(portfolio.get_positions()))

    # def test_add_orders(self):
    #     orders = []

    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     order = portfolio_manager.create_order(
    #         target_symbol=self.TARGET_SYMBOL_A,
    #         amount=1,
    #         price=self.get_price(self.TARGET_SYMBOL_A).price,
    #     )
    #     order.reference_id = 1
    #     db.session.commit()
    #     orders.append(order)

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_orders(orders)

    # def test_add_position(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_position(
    #         Position(target_symbol=self.TARGET_SYMBOL_C, amount=20)
    #     )

    #     self.assertEqual(2, len(portfolio.get_positions()))

    # def test_add_positions(self):
    #     positions = [
    #         Position(target_symbol=self.TARGET_SYMBOL_C, amount=20),
    #         Position(target_symbol=self.TARGET_SYMBOL_D, amount=20)
    #     ]

    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_positions(positions)

    #     self.assertEqual(3, len(portfolio.get_positions()))

    # def test_get_position(self):
    #     positions = [
    #         Position(symbol=self.TARGET_SYMBOL_B, amount=20),
    #         Position(symbol=self.TARGET_SYMBOL_C, amount=20)
    #     ]

    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_positions(positions)

    #     self.assertEqual(3, len(portfolio.get_positions()))

    #     position_b = portfolio.get_position(self.TARGET_SYMBOL_B)
    #     position_c = portfolio.get_position(self.TARGET_SYMBOL_C)

    #     self.assertIsNotNone(position_b)
    #     self.assertIsNotNone(position_c)

    #     self.assertEqual(
    #           self.TARGET_SYMBOL_B, position_b.get_target_symbol()
    #     )
    #     self.assertEqual(
    #           self.TARGET_SYMBOL_C, position_c.get_target_symbol()
    #     )

    # def test_get_positions(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)

    #     self.assertIsNotNone(portfolio.get_positions())
    #     self.assertEqual(1, len(portfolio.get_positions()))

    # def test_get_orders(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     orders = [
    #         Order.from_dict(
    #             {
    #                 "reference_id": 2,
    #                 "target_symbol": self.TARGET_SYMBOL_A,
    #                 "trading_symbol": "usdt",
    #                 "amount": 4,
    #                 "price": self.get_price(self.TARGET_SYMBOL_A).price,
    #                 "status": OrderStatus.PENDING.value,
    #                 "order_side": OrderSide.BUY.value,
    #                 "order_type": OrderType.LIMIT.value
    #             }
    #         ),
    #         Order.from_dict(
    #             {
    #                 "reference_id": 3,
    #                 "target_symbol": self.TARGET_SYMBOL_A,
    #                 "trading_symbol": "usdt",
    #                 "amount": 4,
    #                 "price": self.get_price(self.TARGET_SYMBOL_A).price,
    #                 "status": OrderStatus.CLOSED.value,
    #                 "initial_price": self.get_price(
    #                     self.TARGET_SYMBOL_A).price,
    #                 "order_side": OrderSide.BUY.value,
    #                 "order_type": OrderType.LIMIT.value
    #             }
    #         )
    #     ]

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     portfolio.add_orders(orders)

    #     self.assertEqual(2, len(portfolio.get_orders()))
    #     self.assertEqual(
    #         1, len(portfolio.get_orders(status=OrderStatus.CLOSED))
    #     )
    #     self.assertEqual(
    #         1, len(portfolio.get_orders(status=OrderStatus.PENDING))
    #     )

    #     self.assertEqual(
    #         0, len(portfolio.get_orders(status=OrderStatus.TO_BE_SENT))
    #     )
    #     self.assertEqual(
    #         0, len(portfolio.get_orders(order_side=OrderSide.SELL))
    #     )
    #     self.assertEqual(
    #         0, len(portfolio.get_orders(order_type=OrderType.MARKET))
    #     )
    #     self.assertEqual(
    #         1, len(portfolio.get_orders(
    #             status=OrderStatus.PENDING,
    #             order_type=OrderType.LIMIT,
    #             order_side=OrderSide.BUY
    #         ))
    #     )
    #     self.assertEqual(
    #         1, len(portfolio.get_orders(
    #             status=OrderStatus.CLOSED,
    #             order_type=OrderType.LIMIT,
    #             order_side=OrderSide.BUY
    #         ))
    #     )

    # def test_from_dict(self):
    #     portfolio = Portfolio.from_dict(
    #         {
    #             "identifier": "BINANCE",
    #             "trading_symbol": "USDT",
    #             "market": "BINANCE",
    #             "positions": [
    #                 {"symbol": "USDT", "amount": 10000},
    #                 {"symbol": "DOT", "amount": 40},
    #                 {"symbol": "BTC", "amount": 0.04},
    #             ]
    #         }
    #     )
    #     self.assertIsNotNone(portfolio.get_identifier())
    #     self.assertIsNotNone(portfolio.get_trading_symbol())
    #     self.assertIsNotNone(portfolio.get_unallocated())
    #     self.assertIsNotNone(portfolio.get_positions())
    #     self.assertEqual(3, len(portfolio.get_positions()))
    #     self.assertEqual(0, len(portfolio.get_orders()))

    # def test_from_dict_with_orders(self):
    #     portfolio = Portfolio(
    #         orders=[
    #             Order(
    #                 reference_id=2,
    #                 trading_symbol="USDT",
    #                 target_symbol=self.TARGET_SYMBOL_A,
    #                 status=OrderStatus.PENDING,
    #                 price=10,
    #                 amount=10,
    #                 order_side=OrderSide.BUY,
    #                 order_type=OrderType.LIMIT
    #             )
    #         ],
    #         identifier="BINANCE",
    #         trading_symbol="USDT",
    #         positions=[
    #             Position(amount=10, symbol=self.TARGET_SYMBOL_A, price=10),
    #             Position(amount=10, symbol="USDT")
    #         ],
    #     )
    #     self.assertIsNotNone(portfolio.get_identifier())
    #     self.assertIsNotNone(portfolio.get_trading_symbol())
    #     self.assertIsNotNone(portfolio.get_unallocated())
    #     self.assertIsNotNone(portfolio.get_positions())
    #     self.assertEqual(2, len(portfolio.get_positions()))
    #     self.assertEqual(1, len(portfolio.get_orders()))

    # def test_to_dict(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
    #     data = portfolio.to_dict()
    #     self.assertIsNotNone(data)

    # def test_update_positions(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)

    #     positions = [
    #         Position(symbol=self.TARGET_SYMBOL_A, amount=4),
    #         Position(symbol=self.TARGET_SYMBOL_B, amount=20),
    #         Position(symbol=self.TARGET_SYMBOL_C, amount=20)
    #     ]

    #     self.assertEqual(1, len(portfolio.get_positions()))
    #     portfolio.add_positions(positions)
    #     self.assertEqual(4, len(portfolio.get_positions()))

    #     for position in portfolio.get_positions():
    #         self.assertTrue(isinstance(position, Position))

    #     position_a = portfolio.get_position(self.TARGET_SYMBOL_A)
    #     position_b = portfolio.get_position(self.TARGET_SYMBOL_B)
    #     position_c = portfolio.get_position(self.TARGET_SYMBOL_C)

    #     self.assertEqual(4, position_a.get_amount())
    #     self.assertEqual(20, position_b.get_amount())
    #     self.assertEqual(20, position_c.get_amount())

    # def test_update_orders(self):
    #     portfolio_manager = self.algo_app.algorithm \
    #         .get_portfolio_manager("default")

    #     portfolio = portfolio_manager.get_portfolio(algorithm_context=None)

    #     orders = [
    #         Order.from_dict(
    #             {
    #                 "reference_id": 1,
    #                 "target_symbol": self.TARGET_SYMBOL_A,
    #                 "trading_symbol": "usdt",
    #                 "amount": 4,
    #                 "price": self.get_price(self.TARGET_SYMBOL_A).price,
    #                 "initial_price": self
    #                 .get_price(self.TARGET_SYMBOL_A).price,
    #                 "status": OrderStatus.CLOSED.value,
    #                 "order_side": OrderSide.BUY.value,
    #                 "order_type": OrderType.LIMIT.value
    #             }
    #         ),
    #         Order.from_dict(
    #             {
    #                 "reference_id": 2,
    #                 "target_symbol": self.TARGET_SYMBOL_A,
    #                 "trading_symbol": "usdt",
    #                 "amount": 4,
    #                 "price": self.get_price(self.TARGET_SYMBOL_A).price,
    #                 "status": OrderStatus.PENDING.value,
    #                 "order_side": OrderSide.BUY.value,
    #                 "order_type": OrderType.LIMIT.value
    #             }
    #         ),
    #         Order.from_dict(
    #             {
    #                 "reference_id": 3,
    #                 "target_symbol": self.TARGET_SYMBOL_A,
    #                 "trading_symbol": "usdt",
    #                 "amount": 4,
    #                 "price": self.get_price(self.TARGET_SYMBOL_A).price,
    #                 "status": OrderStatus.CLOSED.value,
    #                 "initial_price": self
    #                 .get_price(self.TARGET_SYMBOL_A).price,
    #                 "order_side": OrderSide.BUY.value,
    #                 "order_type": OrderType.LIMIT.value
    #             }
    #         )
    #     ]

    #     portfolio.add_orders(orders)
    #     order_one = portfolio.get_order(2)
    #     self.assertTrue(OrderStatus.PENDING.equals(order_one.get_status()))
    #     self.assertEqual(3, len(portfolio.get_orders()))
