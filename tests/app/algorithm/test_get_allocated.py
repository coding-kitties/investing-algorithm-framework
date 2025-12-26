from typing import Dict, Any
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    MarketCredential, PortfolioConfiguration
from tests.resources import TestBase


class StrategyOne(TradingStrategy):
    id = "strategy_one"
    time_unit = TimeUnit.SECOND
    interval = 2

    def run_strategy(
        self,
        context,
        data=None,
    ):
        context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            order_side="BUY",
            price=10,
        )

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


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

    def test_get_allocated(self):
        self.app.add_strategy(StrategyOne)

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={
                "bid": 10,
                "ask": 10,
                "last": 10

            }
        ):
            self.app.run(number_of_iterations=1)
            order_service = self.app.container.order_service()
            self.assertEqual(1, order_service.count())
            order_service.check_pending_orders()
            self.assertNotEqual(0, self.app.context.get_allocated())
            self.assertNotEqual(0, self.app.context.get_allocated("BITVAVO"))
            self.assertNotEqual(0, self.app.context.get_allocated("bitvavo"))
