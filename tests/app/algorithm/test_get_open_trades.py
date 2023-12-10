import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, CSVTickerMarketDataSource
from tests.resources import TestBase, MarketServiceStub


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
                market="BITVAVO",
                api_key="test",
                secret_key="test",
                trading_symbol="EUR"
            )
        )
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                self.resource_dir,
                "market_data_sources",
                "TICKER_BTC-EUR_BITVAVO_2021-06-02:00:00_2021-06-26:00:00.csv"
            )
        ))
        self.app.container.market_service.override(MarketServiceStub())
        self.app.initialize()

    def test_get_open_trades(self):
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=20
        )
        order = self.app.algorithm.get_order()
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_open_trades("BTC")))
        trade = self.app.algorithm.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_price)
        self.assertIsNone(trade.closed_at)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=20
        )
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))
        order_service.check_pending_orders()
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))
