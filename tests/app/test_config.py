import os

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    DATABASE_DIRECTORY_NAME, DATABASE_DIRECTORY_PATH, DATABASE_NAME, \
    ENVIRONMENT, Environment, BacktestDateRange
from tests.resources import random_string, TestBase

TEST_VALUE = random_string(10)



class TestConfig(TestBase):
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
    ATTRIBUTE_ONE = "ATTRIBUTE_ONE"

    def tearDown(self) -> None:
        super().tearDown()

        database_dir = os.path.join(
            self.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

            os.rmdir(database_dir)

    def test_config(self):
        self.app.set_config(self.ATTRIBUTE_ONE, TEST_VALUE)
        self.app.initialize_config()
        self.assertIsNotNone(self.app.config)
        self.assertIsNotNone(self.app.config[self.ATTRIBUTE_ONE])

    def test_resource_directory_exists(self):
        self.app.set_config(self.ATTRIBUTE_ONE, TEST_VALUE)
        self.app.initialize_config()
        self.assertIsNotNone(self.app.config)
        self.assertIsNotNone(self.app.config[RESOURCE_DIRECTORY])

    def test_config_production(self):
        self.app.set_config(ENVIRONMENT, Environment.PROD.value)
        self.app.initialize_config()
        self.app.initialize_services()
        self.assertIsNotNone(self.app.config[RESOURCE_DIRECTORY])
        self.assertIsNotNone(self.app.config[ENVIRONMENT])
        self.assertEqual(
            self.app.config[ENVIRONMENT], Environment.PROD.value
        )
        self.assertIsNotNone(self.app.config[DATABASE_DIRECTORY_NAME])
        self.assertEqual(
            "databases", self.app.config[DATABASE_DIRECTORY_NAME]
        )
        self.assertIsNotNone(self.app.config[DATABASE_NAME])
        self.assertEqual(
            "prod-database.sqlite3", self.app.config[DATABASE_NAME]
        )
        self.assertIsNotNone(self.app.config[DATABASE_DIRECTORY_NAME])
        database_directory_path = os.path.join(
            self.app.config[RESOURCE_DIRECTORY],
            self.app.config[DATABASE_DIRECTORY_NAME]
        )
        self.assertEqual(
            database_directory_path, self.app.config[DATABASE_DIRECTORY_PATH]
        )
