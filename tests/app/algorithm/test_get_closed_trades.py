from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


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


    def test_get_open_trades(self):
        self.app.add_strategy(StrategyOne)
        order = self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=20
        )
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.context.get_closed_trades()))
        order_service = self.app.container.order_service()

        with patch.object(
                self.app.container.data_provider_service(),
                "get_ticker_data",
                return_value={
                    "bid": 10,
                    "ask": 10,
                    "last": 10

                }
        ):

            order_service.check_pending_orders()
            self.assertEqual(0, len(self.app.context.get_closed_trades()))
            trade = self.app.context.get_trades()[0]
            self.assertEqual(10, trade.open_price)
            self.assertEqual(20, trade.amount)
            self.assertEqual("BTC", trade.target_symbol)
            self.assertEqual("EUR", trade.trading_symbol)
            self.assertIsNone(trade.closed_at)
            self.app.context.create_limit_order(
                target_symbol="BTC",
                price=10,
                order_side="SELL",
                amount=20
            )
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_closed_trades()))
