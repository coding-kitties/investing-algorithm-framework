from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch, MagicMock

from investing_algorithm_framework.domain import DataSource, DataType, \
    OperationalException
from investing_algorithm_framework.infrastructure import \
    CCXTTickerDataProvider


class TestCCXTTickerDataProviderHasData(TestCase):
    """Tests for CCXTTickerDataProvider.has_data()"""

    def test_returns_false_for_non_ticker_data_type(self):
        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            market="binance",
            symbol="BTC/USDT",
            data_type="ohlcv",
        )
        self.assertFalse(provider.has_data(data_source))

    @patch("investing_algorithm_framework.infrastructure"
           ".data_providers.ccxt.ccxt")
    def test_returns_true_when_symbol_exists(self, mock_ccxt_module):
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {
            "BTC/USDT": {}, "ETH/USDT": {}
        }
        mock_exchange_class = MagicMock(return_value=mock_exchange)
        mock_ccxt_module.binance = mock_exchange_class

        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            market="binance",
            symbol="BTC/USDT",
            data_type="ticker",
        )
        self.assertTrue(provider.has_data(data_source))

    @patch("investing_algorithm_framework.infrastructure"
           ".data_providers.ccxt.ccxt")
    def test_returns_false_when_symbol_not_found(self, mock_ccxt_module):
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"ETH/USDT": {}}
        mock_exchange_class = MagicMock(return_value=mock_exchange)
        mock_ccxt_module.binance = mock_exchange_class

        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            market="binance",
            symbol="BTC/USDT",
            data_type="ticker",
        )
        self.assertFalse(provider.has_data(data_source))

    @patch("investing_algorithm_framework.infrastructure"
           ".data_providers.ccxt.ccxt")
    def test_defaults_market_to_binance(self, mock_ccxt_module):
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"BTC/USDT": {}}
        mock_exchange_class = MagicMock(return_value=mock_exchange)
        mock_ccxt_module.binance = mock_exchange_class

        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            symbol="BTC/USDT",
            data_type="ticker",
        )
        self.assertTrue(provider.has_data(data_source))
        mock_ccxt_module.binance.assert_called_once()


class TestCCXTTickerDataProviderGetData(TestCase):
    """Tests for CCXTTickerDataProvider.get_data()"""

    @patch("investing_algorithm_framework.infrastructure"
           ".data_providers.ccxt.CCXTOHLCVDataProvider.initialize_exchange")
    def test_returns_ticker_dict(self, mock_init_exchange):
        mock_exchange = MagicMock()
        mock_exchange.fetch_ticker.return_value = {
            "datetime": "2024-01-15T12:00:00Z",
            "high": 43500.0,
            "low": 42500.0,
            "bid": 43000.0,
            "ask": 43010.0,
            "open": 42800.0,
            "close": 43100.0,
            "last": 43050.0,
            "baseVolume": 1234.56,
        }
        mock_init_exchange.return_value = mock_exchange

        provider = CCXTTickerDataProvider(
            symbol="BTC/USDT", market="binance"
        )
        provider.config = {}
        result = provider.get_data()

        self.assertEqual(result["symbol"], "BTC/USDT")
        self.assertEqual(result["market"], "BINANCE")
        self.assertEqual(result["last"], 43050.0)
        self.assertEqual(result["bid"], 43000.0)
        self.assertEqual(result["ask"], 43010.0)
        self.assertEqual(result["volume"], 1234.56)
        mock_exchange.fetch_ticker.assert_called_once_with("BTC/USDT")

    def test_raises_when_market_not_set(self):
        provider = CCXTTickerDataProvider(symbol="BTC/USDT")
        with self.assertRaises(OperationalException):
            provider.get_data()

    def test_raises_when_symbol_not_set(self):
        provider = CCXTTickerDataProvider(market="binance")
        with self.assertRaises(OperationalException):
            provider.get_data()


class TestCCXTTickerDataProviderCopy(TestCase):
    """Tests for CCXTTickerDataProvider.copy()"""

    def test_copy_returns_new_instance(self):
        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            market="binance",
            symbol="BTC/USDT",
            data_type="ticker",
        )
        copied = provider.copy(data_source)
        self.assertIsInstance(copied, CCXTTickerDataProvider)
        self.assertEqual(copied.symbol, "BTC/USDT")
        self.assertEqual(copied.market, "BINANCE")

    def test_copy_raises_when_market_missing(self):
        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            symbol="BTC/USDT",
            data_type="ticker",
        )
        with self.assertRaises(OperationalException):
            provider.copy(data_source)

    def test_copy_raises_when_symbol_missing(self):
        provider = CCXTTickerDataProvider()
        data_source = DataSource(
            market="binance",
            data_type="ticker",
        )
        with self.assertRaises(OperationalException):
            provider.copy(data_source)


class TestCCXTTickerDataProviderBacktest(TestCase):
    """Tests for backtest-related methods"""

    def test_prepare_backtest_data_is_noop(self):
        provider = CCXTTickerDataProvider()
        # Should not raise
        provider.prepare_backtest_data(
            backtest_start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            backtest_end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

    def test_get_backtest_data_returns_none(self):
        provider = CCXTTickerDataProvider()
        result = provider.get_backtest_data(
            backtest_index_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )
        self.assertIsNone(result)


class TestCCXTTickerDataProviderAttributes(TestCase):
    """Tests for class attributes and initialization"""

    def test_data_type_is_ticker(self):
        self.assertEqual(CCXTTickerDataProvider.data_type, DataType.TICKER)

    def test_default_identifier(self):
        provider = CCXTTickerDataProvider()
        self.assertEqual(
            provider.data_provider_identifier,
            "ccxt_ticker_data_provider"
        )

    def test_custom_identifier(self):
        provider = CCXTTickerDataProvider(
            data_provider_identifier="my_custom_id"
        )
        self.assertEqual(
            provider.data_provider_identifier,
            "my_custom_id"
        )
