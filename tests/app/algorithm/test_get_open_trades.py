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
        self.app.container.market_service.override(MarketServiceStub(None))
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

    def test_get_open_trades_with_close_trades(self):
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=5
        )
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=5
        )
        order = self.app.algorithm.get_order()
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, len(self.app.algorithm.get_open_trades("BTC")))
        trade = self.app.algorithm.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(5, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_price)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(
            0,
            len(self.app.algorithm.get_orders(order_side="SELL", status="OPEN"))
        )
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=5
        )
        self.assertEqual(
            1,
            len(
                self.app.algorithm.get_orders(order_side="SELL", status="OPEN")
            )
        )
        self.assertEqual(1, len(self.app.algorithm.get_open_trades("BTC")))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=5
        )
        self.assertEqual(2, len(
            self.app.algorithm.get_orders(order_side="SELL", status="OPEN"))
        )
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))

    def test_get_open_trades_with_close_trades_of_partial_buy_orders(self):
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=5
        )
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=5
        )
        order = self.app.algorithm.get_order()
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.algorithm.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, len(self.app.algorithm.get_open_trades("BTC")))
        trade = self.app.algorithm.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(5, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_price)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(
            0,
            len(self.app.algorithm.get_orders(order_side="SELL",
                                              status="OPEN"))
        )
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=2.5
        )
        self.assertEqual(
            1,
            len(
                self.app.algorithm.get_orders(order_side="SELL", status="OPEN")
            )
        )
        open_trades = self.app.algorithm.get_open_trades("BTC")
        self.assertEqual(2.5, open_trades[0].amount)
        self.assertEqual(5, open_trades[1].amount)
        self.app.algorithm.check_pending_orders()
        open_trades = self.app.algorithm.get_open_trades("BTC")
        self.assertEqual(2.5, open_trades[0].amount)
        self.assertEqual(5, open_trades[1].amount)
        self.assertEqual(2, len(self.app.algorithm.get_open_trades("BTC")))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=5
        )
        trades = self.app.algorithm.get_open_trades()
        self.assertEqual(1, len(trades))
        self.assertEqual(2.5, trades[0].amount)
        self.app.algorithm.check_pending_orders()
        trades = self.app.algorithm.get_open_trades()
        self.assertEqual(1, len(trades))
        self.assertEqual(2.5, trades[0].amount)
