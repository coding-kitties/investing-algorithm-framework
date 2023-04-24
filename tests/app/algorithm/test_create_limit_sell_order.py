import os

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, OrderType, OrderSide, \
    OrderStatus
from tests.resources import TestBase, MarketServiceStub


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
            amount_target_symbol=1,
            price=10,
            side="SELL",
        )


class Test(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
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
        self.app.add_strategy(StrategyOne)
        self.app.create_portfolios()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        order_service = self.app.container.order_service()
        order_service.create(
            {
                "target_symbol": "BTC",
                "price": 10,
                "amount_target_symbol": 1,
                "type": OrderType.LIMIT.value,
                "side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.PENDING.value,
                "trading_symbol": portfolio.trading_symbol,
            },
        )
        order_service.check_pending_orders()

    def test_create_limit_sell_order(self):
        position_service = self.app.container.position_service()
        order_service = self.app.container.order_service()
        trading_symbol_position = position_service.find({"symbol": "USDT"})
        self.assertEqual(990, trading_symbol_position.amount)
        self.app.run(number_of_iterations=1, sync=False)
        trading_symbol_position = position_service.find({"symbol": "USDT"})
        self.assertEqual(990, trading_symbol_position.amount)
        order_service.check_pending_orders()
        btc_position = position_service.find({"symbol": "BTC"})
        trading_symbol_position = position_service.find({"symbol": "USDT"})
        self.assertEqual(0, btc_position.amount)
        self.assertEqual(1000, trading_symbol_position.amount)
