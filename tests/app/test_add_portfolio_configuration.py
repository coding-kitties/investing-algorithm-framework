import os
from unittest import TestCase

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, Algorithm, MarketCredential
from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from tests.resources import MarketServiceStub, TestBase


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
        "EUR": 1000,
    }

    def test_add(self):
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        self.assertEqual(1, self.app.algorithm.portfolio_service.count())
        self.assertEqual(1000, self.app.algorithm.get_unallocated())
