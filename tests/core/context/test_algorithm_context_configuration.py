from unittest import TestCase
from investing_algorithm_framework.core.context import \
    AlgorithmContextConfiguration
from investing_algorithm_framework.configuration.constants import API_KEY, \
    SECRET_KEY, CCXT_ENABLED, MARKET
from investing_algorithm_framework.configuration.settings import DevConfig
from tests.resources.utils import random_string


class Test(TestCase):

    def setUp(self) -> None:
        super(Test, self).setUp()

    def test_config_initialization(self):
        config = DevConfig()
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)

        for attribute_key in config:
            self.assertEqual(
                context_config.get(attribute_key), config[attribute_key]
            )

    def test_ccxt_enabled(self):
        config = DevConfig()
        config.set(CCXT_ENABLED, True)
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)

        for attribute_key in config:
            self.assertEqual(
                context_config.get(attribute_key), config[attribute_key]
            )

        self.assertFalse(context_config.ccxt_enabled())

        config.set(MARKET, "binance")
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)
        self.assertTrue(context_config.ccxt_enabled())

    def test_ccxt_api_secret_configured(self):
        config = DevConfig()
        config.set(CCXT_ENABLED, True)
        config.set(MARKET, "binance")
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)

        for attribute_key in config:
            self.assertEqual(
                context_config.get(attribute_key), config[attribute_key]
            )

        self.assertTrue(context_config.ccxt_enabled())
        self.assertFalse(context_config.ccxt_authentication_configured())

        config.set(API_KEY, random_string(10))
        config.set(SECRET_KEY, random_string(10))

        context_config = AlgorithmContextConfiguration()
        context_config.load(config)
        self.assertTrue(context_config.ccxt_enabled())
        self.assertTrue(context_config.ccxt_authentication_configured())
