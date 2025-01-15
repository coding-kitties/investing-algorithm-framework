from investing_algorithm_framework import PortfolioConfiguration, \
    OrderType, OrderSide, OrderStatus, MarketCredential
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
    external_balances = {
        "EUR": 1000
    }
    external_available_symbols = ["BTC/EUR"]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    market_data_source_service = MarketDataSourceServiceStub()

    def test_create_market_sell_order(self):
        portfolio = self.app.algorithm.get_portfolio()
        order_service = self.app.container.order_service()
        order_service.create(
            {
                "target_symbol": "BTC",
                "price": 10,
                "amount": 1,
                "order_type": OrderType.LIMIT.value,
                "order_side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.CREATED.value,
                "trading_symbol": portfolio.trading_symbol,
            },
        )
        position_service = self.app.container.position_service()
        order_service = self.app.container.order_service()
        trading_symbol_position = position_service.find({"symbol": "EUR"})
        self.assertEqual(990, trading_symbol_position.get_amount())
        self.app.run(number_of_iterations=1)
        trading_symbol_position = position_service.find({"symbol": "EUR"})
        self.assertEqual(990, trading_symbol_position.get_amount())
        btc_position = position_service.find({"symbol": "BTC"})
        self.assertEqual(1, btc_position.get_amount())
        self.app.algorithm.create_market_order(
            target_symbol="BTC",
            amount=1,
            order_side="SELL",
        )
        btc_position = position_service.find({"symbol": "BTC"})
        self.assertEqual(0, btc_position.get_amount())
        market_sell_order = order_service.find(
            {"target_symbol": "BTC", "order_side": "SELL"}
        )
        self.assertIsNotNone(market_sell_order)
        self.assertEqual(OrderStatus.CREATED.value, market_sell_order.status)
        self.assertEqual(1, market_sell_order.amount)
        self.assertEqual(None, market_sell_order.price)
