import os
from unittest import TestCase
from datetime import datetime, timezone

from investing_algorithm_framework.services import DataProviderService, \
    MarketCredentialService, ConfigurationService
from investing_algorithm_framework.infrastructure import \
    CCXTOHLCVDataProvider, CSVOHLCVDataProvider
from investing_algorithm_framework.domain import DataProvider, DataType, \
    DataSource, RESOURCE_DIRECTORY, BacktestDateRange


class CustomDataProvider(DataProvider):
    """
    Custom data provider for testing purposes.
    """

    def prepare_backtest_data(
            self,
            backtest_start_date,
            backtest_end_date
    ) -> None:
        pass

    data_type = DataType.CUSTOM
    data_provider_identifier = "twitter"

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        if DataType.CUSTOM.equals(data_source.data_type) and \
            data_source.data_provider_identifier == \
                self.data_provider_identifier:
            return True

        return False

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ):
        return {}

    def get_backtest_data(
        self,
        date,
        backtest_start_date = None,
        backtest_end_date = None,
    ):
        return {}

    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None,
    ) -> None:
        print(f"Preparing backtest data from {backtest_start_date} to {backtest_end_date} for {symbol} on {market}")

    def copy(self, data_source: DataSource) -> "DataProvider":
        """
        Create a copy of the data provider with the given data source.
        """
        return CustomDataProvider()


class TestDataProviderService(TestCase):

    def setUp(self):
        self.resource_directory = os.path.join(
            os.path.dirname(__file__),
            "..", "resources"
        )

    def test_add_data_provider(self):
        """
        Test adding a data provider to the service.
        This test checks if a data provider can be added and if
        the given data provider is correctly stored in the right index
        """
        service: DataProviderService = DataProviderService(
            market_credential_service=MarketCredentialService(),
            configuration_service=ConfigurationService()
        )
        service.add_data_provider(CustomDataProvider())
        self.assertEqual(
            len(service.data_provider_index.data_providers), 1
        )
        self.assertEqual(
            len(service.data_provider_index.data_providers_lookup), 0
        )

    def test_add_ohlcv_data_provider(self):
        data_source_one = DataSource(
            market="BINANCE",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="BTC/EUR-ohlcv-1h"
        )
        data_source_two = DataSource(
            market="BINANCE",
            symbol="ETH/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="ETH/EUR-ohlcv-1h"
        )

        configuration_service = ConfigurationService()
        configuration_service.add_value(
            RESOURCE_DIRECTORY, self.resource_directory
        )

        service: DataProviderService = DataProviderService(
            market_credential_service=MarketCredentialService(),
            configuration_service=configuration_service
        )
        service.reset()
        service.add_data_provider(CCXTOHLCVDataProvider())
        service.index_data_providers([data_source_one])

        self.assertEqual(
            len(service.data_provider_index.data_providers), 1
        )
        self.assertEqual(
            len(service.data_provider_index.data_providers_lookup), 1
        )
        self.assertEqual(
            len(service.data_provider_index.ohlcv_data_providers), 1
        )

        # Add second data source
        service.index_data_providers([
            data_source_one, data_source_two
        ])
        self.assertEqual(
            len(service.data_provider_index.data_providers), 1
        )
        self.assertEqual(
            len(service.data_provider_index.data_providers_lookup), 2
        )
        self.assertEqual(
            len(service.data_provider_index.ohlcv_data_providers), 2
        )

        data_provider_one = service.data_provider_index.get(data_source_one)
        data_provider_two = service.data_provider_index.get(data_source_two)

        # MAke sure that the memory addresses of the data providers
        # are different
        self.assertNotEqual(data_provider_one, data_provider_two)

    def test_get_ohlcv_data_ccxt(self):
        """
        Test getting OHLCV data from the data provider service correctly
        gets the ohlcv data from the storage when before the prepare
        backtest data method is called.
        """
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2023, 1, 31, tzinfo=timezone.utc)
        )
        data_source_one = DataSource(
            market="BINANCE",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="BTC/EUR-ohlcv-1h"
        )
        data_source_two = DataSource(
            market="BINANCE",
            symbol="ETH/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="ETH/EUR-ohlcv-1h"
        )
        configuration_service = ConfigurationService()
        configuration_service.add_value(
            RESOURCE_DIRECTORY, self.resource_directory
        )
        service: DataProviderService = DataProviderService(
            market_credential_service=MarketCredentialService(),
            configuration_service=configuration_service
        )
        service.add_data_provider(CCXTOHLCVDataProvider())
        # Add second data source
        service.index_backtest_data_providers(
            [data_source_one, data_source_two],
            backtest_date_range=backtest_date_range
        )
        service.prepare_backtest_data(
            backtest_date_range=backtest_date_range,
        )
        self.assertEqual(
            len(service.data_provider_index.ohlcv_data_providers), 2
        )
        index_date = datetime(2023, 1, 20, tzinfo=timezone.utc)
        data = service.get_ohlcv_data(
            symbol="BTC/EUR",
            market="BINANCE",
            time_frame="1h",
            start_date=index_date,
            end_date=backtest_date_range.end_date
        )
        expected_amount_of_data_points = 11 * 24 + 1 # 20 days * 24 hours
        self.assertEqual(len(data), expected_amount_of_data_points)

    def test_get_ticker_data_with_ohlcv(self):
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2023, 1, 31, tzinfo=timezone.utc)
        )
        data_source_one = DataSource(
            market="BINANCE",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="BTC/EUR-ohlcv-1h"
        )
        data_source_two = DataSource(
            market="BINANCE",
            symbol="ETH/EUR",
            data_type=DataType.OHLCV,
            time_frame="1h",
            window_size=200,
            identifier="ETH/EUR-ohlcv-1h"
        )
        configuration_service = ConfigurationService()
        configuration_service.add_value(
            RESOURCE_DIRECTORY, self.resource_directory
        )
        service: DataProviderService = DataProviderService(
            market_credential_service=MarketCredentialService(),
            configuration_service=configuration_service
        )
        service.add_data_provider(CCXTOHLCVDataProvider())
        # Add second data source
        service.index_backtest_data_providers(
            [data_source_one, data_source_two],
            backtest_date_range=backtest_date_range
        )
        service.prepare_backtest_data(
            backtest_date_range=backtest_date_range,
        )
        self.assertEqual(
            len(service.data_provider_index.ohlcv_data_providers), 2
        )
        index_date = datetime(2023, 1, 20, tzinfo=timezone.utc)
        data = service.get_ticker_data(
            symbol="BTC/EUR",
            market="BINANCE",
            date=index_date,
        )
        self.assertIsNotNone(data)
        self.assertEqual(data["symbol"], "BTC/EUR")
        self.assertEqual(data["market"], "BINANCE")
        self.assertEqual(data["datetime"], index_date)
        self.assertIn("open", data)
        self.assertIn("high", data)
        self.assertIn("low", data)
        self.assertIn("close", data)
        self.assertIn("volume", data)
        self.assertIn("ask", data)
        self.assertIn("bid", data)
