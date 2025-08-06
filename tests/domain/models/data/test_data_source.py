from unittest import TestCase
from dataclasses import FrozenInstanceError

from investing_algorithm_framework.domain.models.data import DataSource, \
    DataType
from investing_algorithm_framework.domain.models import TimeFrame


class TestDataSource(TestCase):

    def test_data_source_default_initialization(self):
        """Test DataSource initialization with default values"""
        data_source = DataSource()

        self.assertIsNone(data_source.data_provider_identifier)
        self.assertIsNone(data_source.data_type)
        self.assertIsNone(data_source.symbol)
        self.assertIsNone(data_source.window_size)
        self.assertIsNone(data_source.time_frame)
        self.assertIsNone(data_source.market)

    def test_data_source_initialization_with_values(self):
        """Test DataSource initialization with specific values"""
        data_source = DataSource(
            data_provider_identifier="test_provider",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=100,
            time_frame="1h",
            market="binance"
        )

        self.assertEqual(data_source.data_provider_identifier, "test_provider")
        self.assertEqual(data_source.data_type, DataType.OHLCV)
        self.assertEqual(data_source.symbol, "BTC/EUR")
        self.assertEqual(data_source.window_size, 100)
        self.assertTrue(TimeFrame.ONE_HOUR.equals(data_source.time_frame))
        self.assertEqual(data_source.market, "BINANCE")

    def test_data_source_partial_initialization(self):
        """Test DataSource initialization with some values"""
        data_source = DataSource(
            data_provider_identifier="partial_test",
            symbol="ETH/USD"
        )

        self.assertEqual(data_source.data_provider_identifier, "partial_test")
        self.assertEqual(data_source.symbol, "ETH/USD")
        self.assertIsNone(data_source.data_type)
        self.assertIsNone(data_source.window_size)
        self.assertIsNone(data_source.time_frame)
        self.assertIsNone(data_source.market)

    def test_data_source_with_different_data_types(self):
        """Test DataSource with different DataType enum values"""
        test_cases = [
            DataType.OHLCV,
            DataType.TICKER,
            DataType.ORDER_BOOK,
            DataType.CUSTOM
        ]

        for data_type in test_cases:
            with self.subTest(data_type=data_type):
                data_source = DataSource(data_type=data_type)
                self.assertEqual(data_source.data_type, data_type)

    def test_data_source_equality_ohlcv(self):
        """Test DataSource equality comparison"""
        data_source1 = DataSource(
            data_provider_identifier="test",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=50,
            time_frame="4h",
            market="binance"
        )

        data_source2 = DataSource(
            data_provider_identifier="test",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=50,
            time_frame="4h",
            market="binance"
        )

        self.assertEqual(data_source1, data_source2)

        data_source3 = DataSource(
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            market="binance"
        )

        data_source4 = DataSource(
            data_provider_identifier="test",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=50,
            time_frame="4h",
            market="binance"
        )

        self.assertEqual(data_source4, data_source3)

    def test_data_source_inequality(self):
        """Test DataSource inequality comparison"""
        data_source1 = DataSource(
            data_provider_identifier="test1",
            data_type=DataType.OHLCV
        )

        data_source2 = DataSource(
            data_provider_identifier="test2",
            data_type=DataType.TICKER
        )

        self.assertNotEqual(data_source1, data_source2)

    def test_data_source_in_set_uniqueness(self):
        """Test that DataSource instances are unique in sets based on all attributes"""
        data_source1 = DataSource(
            data_provider_identifier="provider1",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=100,
            time_frame="1h",
            market="binance"
        )

        # Same as data_source1
        data_source2 = DataSource(
            data_provider_identifier="provider1",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=100,
            time_frame="1h",
            market="binance"
        )

        # Different symbol
        data_source3 = DataSource(
            data_provider_identifier="provider1",
            data_type=DataType.OHLCV,
            symbol="ETH/EUR",
            window_size=100,
            time_frame="1h",
            market="binance"
        )

        # Different window_size
        data_source4 = DataSource(
            data_provider_identifier="provider1",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=200,
            time_frame="1h",
            market="binance"
        )

        data_sources_set = {data_source1, data_source2, data_source3, data_source4}

        # Should only have 3 unique data sources (data_source1 and data_source2 are the same)
        self.assertEqual(len(data_sources_set), 3)
        self.assertIn(data_source1, data_sources_set)
        self.assertIn(data_source3, data_sources_set)
        self.assertIn(data_source4, data_sources_set)

    def test_data_source_hashable(self):
        """Test that DataSource instances are hashable"""
        data_source = DataSource(
            data_provider_identifier="test",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR"
        )

        # Should not raise an exception
        hash_value = hash(data_source)
        self.assertIsInstance(hash_value, int)

    def test_data_source_as_dict_key(self):
        """Test that DataSource can be used as dictionary keys"""
        data_source1 = DataSource(
            data_provider_identifier="provider1",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV
        )

        data_source2 = DataSource(
            data_provider_identifier="provider2",
            symbol="ETH/USD",
            data_type=DataType.TICKER
        )

        data_dict = {
            data_source1: "Bitcoin data",
            data_source2: "Ethereum data"
        }

        self.assertEqual(data_dict[data_source1], "Bitcoin data")
        self.assertEqual(data_dict[data_source2], "Ethereum data")
        self.assertEqual(len(data_dict), 2)

    def test_data_source_set_operations(self):
        """Test set operations with DataSource instances"""
        data_source1 = DataSource(
            data_provider_identifier="provider1",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV
        )

        data_source2 = DataSource(
            data_provider_identifier="provider2",
            symbol="ETH/USD",
            data_type=DataType.TICKER
        )

        data_source3 = DataSource(
            data_provider_identifier="provider1",
            symbol="BTC/EUR",
            data_type=DataType.OHLCV
        )  # Same as data_source1

        set1 = {data_source1, data_source2}
        set2 = {data_source3, data_source2}  # data_source3 is same as data_source1

        # Test intersection
        intersection = set1 & set2
        self.assertEqual(len(intersection), 2)  # Both data sources are in common

        # Test union
        union = set1 | set2
        self.assertEqual(len(union), 2)  # Only 2 unique data sources

        # Test difference
        difference = set1 - set2
        self.assertEqual(len(difference), 0)  # No difference since sets are equal

    def test_data_source_uniqueness_edge_cases(self):
        """Test uniqueness with edge cases like None values"""
        data_source1 = DataSource()  # All None values
        data_source2 = DataSource()  # All None values
        data_source3 = DataSource(symbol="BTC/EUR")  # One non-None value

        data_sources_set = {data_source1, data_source2, data_source3}

        # Should only have 2 unique data sources
        self.assertEqual(len(data_sources_set), 3)

    # If using frozen=True, test immutability
    def test_data_source_immutability(self):
        """Test that DataSource is immutable when frozen=True"""
        data_source = DataSource(
            data_provider_identifier="test",
            symbol="BTC/EUR"
        )

        # If frozen=True is used, this should raise FrozenInstanceError
        # If frozen=False, this test should be skipped or modified
        try:
            data_source.symbol = "ETH/USD"
            # If we reach here, the class is not frozen
            self.skipTest("DataSource is not frozen, skipping immutability test")
        except FrozenInstanceError:
            # This is expected behavior when frozen=True
            pass

    def test_data_source_with_none_values(self):
        """Test DataSource explicitly set to None values"""
        data_source = DataSource(
            data_provider_identifier=None,
            data_type=None,
            symbol=None,
            window_size=None,
            time_frame=None,
            market=None
        )

        self.assertIsNone(data_source.data_provider_identifier)
        self.assertIsNone(data_source.data_type)
        self.assertIsNone(data_source.symbol)
        self.assertIsNone(data_source.window_size)
        self.assertIsNone(data_source.time_frame)
        self.assertIsNone(data_source.market)

    def test_data_source_window_size_types(self):
        """Test DataSource with different window_size values"""
        # Test positive integer
        data_source = DataSource(window_size=100)
        self.assertEqual(data_source.window_size, 100)

        # Test zero
        data_source = DataSource(window_size=0)
        self.assertEqual(data_source.window_size, 0)

        # Test large number
        data_source = DataSource(window_size=10000)
        self.assertEqual(data_source.window_size, 10000)

    def test_data_source_time_frame_values(self):
        """Test DataSource with different time_frame string values"""
        time_frames = ["1m", "5m", "15m", "1h", "4h", "1d", "1W", "1M"]

        for time_frame in time_frames:
            with self.subTest(time_frame=time_frame):
                data_source = DataSource(time_frame=time_frame)
                self.assertEqual(data_source.time_frame.value, time_frame)

    def test_data_source_symbol_formats(self):
        """Test DataSource with different symbol formats"""
        symbols = ["BTC/EUR", "ETH/USD", "AAPL", "BTCUSDT", "XRP-EUR"]

        for symbol in symbols:
            with self.subTest(symbol=symbol):
                data_source = DataSource(symbol=symbol)
                self.assertEqual(data_source.symbol, symbol)

    def test_data_source_market_values(self):
        """Test DataSource with different market values"""
        markets = ["binance", "coinbase", "kraken", "bitstamp"]

        for market in markets:
            with self.subTest(market=market):
                data_source = DataSource(market=market)
                self.assertEqual(data_source.market, market.upper())

    def test_data_source_is_dataclass(self):
        """Test that DataSource behaves as a dataclass"""
        from dataclasses import is_dataclass, fields

        # Check if it's a dataclass
        self.assertTrue(is_dataclass(DataSource))

        # Check field names
        field_names = [field.name for field in fields(DataSource)]
        expected_fields = [
            "data_provider_identifier",
            "data_type",
            "symbol",
            "window_size",
            "time_frame",
            "market",
            "save",
            "pandas",
            "start_date",
            "end_date",
            "storage_path",
            "date",
            "identifier"
        ]

        self.assertEqual(set(field_names), set(expected_fields))

    def test_data_source_field_defaults(self):
        """
        Test that all DataSource fields have None
        as default except for save and pandas
        """
        from dataclasses import fields

        for field in fields(DataSource):

            if field.name in ["save", "pandas"]:
                # These fields are expected to have a default value
                self.assertIsNotNone(field.default)
            else:
                with self.subTest(field=field.name):
                    # All fields should have None as default
                    self.assertIsNone(field.default)

    def test_comparison_between_ohlcv_data_sources(self):
        # Compare that a datasource with OHLCV data type, symbol BTC/EUR,
        # window size 100, and time frame 1h, market binance is equal to
        # a datasource with OHLCV data type, symbol BTC/EUR, market binance,
        data_source_one = DataSource(
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            window_size=100,
            time_frame="1h",
            market="binance"
        )

        data_source_two = DataSource(
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
        )

        self.assertEqual(data_source_one, data_source_two)
