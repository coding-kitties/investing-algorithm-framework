from datetime import datetime

from investing_algorithm_framework import DataProvider, DataSource, DataType, \
    PortfolioConfiguration, MarketCredential, TradingStrategy
from tests.resources import TestBase


class DataProviderTest(DataProvider):
    data_type = DataType.CUSTOM
    data_provider_identifier = "DataProviderTest"

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> bool:
        return True

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False
    ):
        return "provided"

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date
    ) -> None:
        pass

    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None
    ):
        return "provided"

    def copy(self, data_source: DataSource) -> "DataProvider":
        return DataProviderTest()


class TestCustomDataProviderStrategy(TradingStrategy):
    time_unit = "SECOND"
    interval = 10
    data_sources = [DataSource(data_type=DataType.CUSTOM, identifier="custom_data")]

    def run_strategy(self, context, data):
        assert data["custom_data"] == "provided", "Data should be provided by the custom data provider"

class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            initial_balance=1000,
            trading_symbol="EUR",
            market="BITVAVO"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="test_api_key",
            secret_key="test_api_secret",
        )
    ]

    def test_add_data_provider(self):
        self.app.add_data_provider(DataProviderTest)
        self.app.add_strategy(TestCustomDataProviderStrategy())
        self.app.run(number_of_iterations=1)
