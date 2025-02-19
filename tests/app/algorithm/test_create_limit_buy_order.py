from investing_algorithm_framework import PortfolioConfiguration, \
    OrderStatus, MarketCredential
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
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
    market_data_source_service = MarketDataSourceServiceStub()

    def count_decimals(self, number):
        decimal_str = str(number)
        if '.' in decimal_str:
            return len(decimal_str.split('.')[1])
        else:
            return 0

    def test_create_limit_buy_order(self):
        self.app.run(number_of_iterations=1)
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1,
            order_repository.count(
                {"order_type": "LIMIT", "order_side": "BUY"}
            )
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)

    def test_create_limit_buy_order_with_percentage_of_portfolio(self):
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            percentage_of_portfolio=20,
            precision=0
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository
            .count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(1000, portfolio.get_net_size())
        self.assertEqual(800, portfolio.get_unallocated())
