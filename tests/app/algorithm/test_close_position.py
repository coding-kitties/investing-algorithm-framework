import os
from decimal import Decimal
from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    CSVOHLCVDataProvider, MarketCredential
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


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

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.app.add_data_provider(CSVOHLCVDataProvider(
            data_provider_identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            storage_path=os.path.join(
                self.resource_directory,
                "test_data",
                "ohlcv",
                "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-08_2023-12-02-00-00.csv"
            ),
            time_frame="1h",
        ), priority=1)

    def test_close_position(self):
        self.app.add_strategy(StrategyOne)
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={
                "bid": 990,
                "ask": 1000,
                "last": 995

            }
        ):
            btc_position = self.app.context.get_position("BTC")
            self.assertIsNotNone(btc_position)
            self.assertEqual(0, btc_position.get_amount())

            order_service = self.app.container.order_service()
            order_service.check_pending_orders()

            btc_position = self.app.context.get_position("BTC")
            self.assertIsNotNone(btc_position.get_amount())
            self.assertEqual(Decimal(1), btc_position.get_amount())
            self.assertNotEqual(Decimal(990), trading_symbol_position.get_amount())

            self.app.context.close_position(btc_position)
            self.app.run(number_of_iterations=1)

            btc_position = self.app.context.get_position("BTC")
            self.assertEqual(Decimal(0), btc_position.get_amount())