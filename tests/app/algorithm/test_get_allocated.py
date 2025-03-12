from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    MarketCredential, PortfolioConfiguration
from tests.resources import TestBase, RandomPriceMarketDataSourceServiceStub, \
    MarketDataSourceServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(
        self,
        algorithm,
        market_date=None,
        **kwargs
    ):
        algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            order_side="BUY",
            price=10,
        )


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

    def test_get_allocated(self):
        self.app.container.market_data_source_service.override(
            RandomPriceMarketDataSourceServiceStub(
                None,
                None,
                None
            )
        )
        self.app.run(number_of_iterations=1)
        order_service = self.app.container.order_service()
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertEqual(1, order_service.count())
        order_service.check_pending_orders()
        self.assertNotEqual(0, self.app.context.get_allocated())
        self.assertNotEqual(0, self.app.context.get_allocated("BITVAVO"))
        self.assertNotEqual(0, self.app.context.get_allocated("bitvavo"))
