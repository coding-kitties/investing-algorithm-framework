from investing_algorithm_framework import TradingTimeUnit, \
    TradingDataTypes, Ticker, OrderBook, OperationalException
from tests.resources import TestBase


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test_provide_ohlcv(self) -> None:
        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbol="BTC",
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_DAY,
            limit=5,
            market="binance"
        )

        self.assertEqual(5, len(data["ohlcv"].get_data()))

        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbol="BTC",
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_MINUTE,
            limit=7200,
            market="binance"
        )

        self.assert_almost_equal(7200, len(data["ohlcv"].get_data()), 100)

        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbol="BTC",
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_DAY,
            limit=100,
            market="binance"
        )

        self.assertEqual(100, len(data["ohlcv"].get_data()))

    def test_provide_ohlcvs(self):

        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbols=["BTC", "DOT"],
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_DAY,
            limit=5,
            market="binance"
        )

        for ohlcv_data in data["ohlcvs"]:
            self.assertEqual(5, len(ohlcv_data.get_data()))

        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbols=["BTC", "DOT"],
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_MINUTE,
            limit=7200,
            market="binance"
        )

        for ohlcv_data in data["ohlcvs"]:
            self.assert_almost_equal(7200, len(ohlcv_data.get_data()), 100)

        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbols=["BTC", "DOT"],
            trading_symbol="USDT",
            trading_time_unit=TradingTimeUnit.ONE_DAY,
            limit=100,
            market="binance"
        )

        for ohlcv_data in data["ohlcvs"]:
            self.assertEqual(100, len(ohlcv_data.get_data()))

    def test_ticker(self):
        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.TICKER,
            target_symbol="BTC",
            trading_symbol="USDT",
            market="binance"
        )

        self.assertTrue(isinstance(data["ticker"], Ticker))

    def test_tickers(self):
        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.TICKER,
            target_symbols=["BTC", "DOT"],
            trading_symbol="USDT",
            market="binance"
        )

        for ticker in data["tickers"]:
            self.assertTrue(isinstance(ticker, Ticker))

    def test_order_book(self):
        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.ORDER_BOOK,
            target_symbol="BTC",
            trading_symbol="USDT",
            market="binance"
        )

        self.assertTrue(isinstance(data["order_book"], OrderBook))

    def test_order_books(self):
        data = self.algo_app.algorithm.get_data(
            trading_data_type=TradingDataTypes.ORDER_BOOK,
            target_symbols=["BTC", "DOT"],
            trading_symbol="USDT",
            market="binance"
        )

        for order_book in data["order_books"]:
            self.assertTrue(isinstance(order_book, OrderBook))

    def test_raw(self):

        with self.assertRaises(OperationalException):
            self.algo_app.algorithm.get_data(
                trading_data_type=TradingDataTypes.RAW,
                target_symbols=["BTC", "DOT"],
                trading_symbol="USDT",
                market="binance"
            )
