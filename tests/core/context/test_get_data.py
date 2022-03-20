import time

from investing_algorithm_framework import TimeUnit, TradingDataTypes
from investing_algorithm_framework.core.workers.strategy_worker import Strategy
from tests.resources import TestBase


class StrategyTestOne(Strategy):
    has_run = False

    def __init__(self):
        super(StrategyTestOne, self)\
            .__init__(time_unit=TimeUnit.SECOND, interval=1)
        StrategyTestOne.has_run = False

    def run_strategy(self, context, **kwargs):
        StrategyTestOne.has_run = True


class StrategyTestTwo(Strategy):
    has_run = False

    def __init__(self):
        super(StrategyTestTwo, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            trading_data_type=TradingDataTypes.TICKER,
            target_symbol=TestBase.TARGET_SYMBOL_A
        )
        StrategyTestTwo.has_run = False

    def run_strategy(self, context, **kwargs):
        StrategyTestTwo.has_run = True


class StrategyTestThree(Strategy):
    has_run = False
    has_ticker = False

    def __init__(self):
        super(StrategyTestThree, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            trading_data_type=TradingDataTypes.TICKER,
            target_symbol=TestBase.TARGET_SYMBOL_A,
            market="test"
        )
        StrategyTestThree.has_run = False
        StrategyTestThree.has_ticker = False

    def run_strategy(self, context, ticker, **kwargs):
        StrategyTestThree.has_run = True

        if ticker is not None:
            StrategyTestThree.has_ticker = True


class StrategyTestFour(Strategy):
    has_run = False
    has_tickers = False

    def __init__(self):
        super(StrategyTestFour, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            target_symbols=[
                TestBase.TARGET_SYMBOL_A, TestBase.TARGET_SYMBOL_B
            ],
            trading_data_type=TradingDataTypes.TICKER,
            market="test"
        )
        StrategyTestFour.has_run = False
        StrategyTestFour.has_tickers = False

    def run_strategy(self, context, tickers, **kwargs):
        StrategyTestFour.has_run = True

        if tickers is not None:
            StrategyTestFour.has_tickers = True


class StrategyTestFive(Strategy):
    has_run = False
    has_order_book = False

    def __init__(self):
        super(StrategyTestFive, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            target_symbol="BTC",
            trading_symbol="USDT",
            trading_data_type=TradingDataTypes.ORDER_BOOK,
            market="test"
        )
        StrategyTestFive.has_run = False
        StrategyTestFive.has_order_book = False

    def run_strategy(self, context, order_book, **kwargs):
        StrategyTestFive.has_run = True

        if order_book is not None:
            StrategyTestFive.has_order_book = True


class StrategyTestSix(Strategy):
    has_run = False
    has_order_books = False

    def __init__(self):
        super(StrategyTestSix, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            target_symbols=[TestBase.TARGET_SYMBOL_A, TestBase.TARGET_SYMBOL_B],
            trading_data_type=TradingDataTypes.ORDER_BOOK,
            market="test"
        )
        StrategyTestSix.has_run = False
        StrategyTestSix.has_order_book = False

    def run_strategy(self, context, order_books, **kwargs):
        StrategyTestSix.has_run = True

        if order_books is not None:
            StrategyTestSix.has_order_books = True


class StrategyTestSeven(Strategy):
    has_run = False
    has_order_books = False
    has_tickers = False

    def __init__(self):
        super(StrategyTestSeven, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            target_symbols=[TestBase.TARGET_SYMBOL_A, TestBase.TARGET_SYMBOL_B],
            trading_data_types=[TradingDataTypes.ORDER_BOOK, TradingDataTypes.TICKER],
            market="test"
        )
        StrategyTestSeven.has_run = False
        StrategyTestSeven.has_order_books = False
        StrategyTestSeven.has_tickers = False

    def run_strategy(self, context, order_books, tickers, **kwargs):
        StrategyTestSeven.has_run = True

        if order_books is not None:
            StrategyTestSeven.has_order_books = True

        if tickers is not None:
            StrategyTestSeven.has_tickers = True


class StrategyTestEight(Strategy):
    has_run = False
    has_order_book = False
    has_ticker = False

    def __init__(self):
        super(StrategyTestEight, self)\
            .__init__(
            time_unit=TimeUnit.SECOND,
            interval=1,
            trading_symbol="USDT",
            target_symbol=TestBase.TARGET_SYMBOL_A,
            trading_data_types=[
                TradingDataTypes.ORDER_BOOK, TradingDataTypes.TICKER
            ],
            market="test"
        )
        StrategyTestEight.has_run = False
        StrategyTestEight.has_order_book = False
        StrategyTestEight.has_ticker = False

    def run_strategy(self, context, **kwargs):
        StrategyTestEight.has_run = True

        if "order_book" in kwargs:
            StrategyTestEight.has_order_book = True

        if "ticker" in kwargs:
            StrategyTestEight.has_ticker = True


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()

    def test_get_data_without_data_provider_specification(self):
        self.algo_app.algorithm.add_strategy(StrategyTestTwo)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestTwo.has_run)

    def test_get_data_with_data_provider_specification_ticker(self):
        self.algo_app.algorithm.add_strategy(StrategyTestThree)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestThree.has_run)
        self.assertTrue(StrategyTestThree.has_ticker)

    def test_get_data_with_ticker(self):
        self.algo_app.algorithm.add_strategy(StrategyTestThree)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestThree.has_run)
        self.assertTrue(StrategyTestThree.has_run)

    def test_get_data_with_tickers(self):
        self.algo_app.algorithm.add_strategy(StrategyTestFour)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestFour.has_run)
        self.assertTrue(StrategyTestFour.has_tickers)

    def test_get_data_with_order_book(self):
        self.algo_app.algorithm.add_strategy(StrategyTestFive)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestFive.has_run)
        self.assertTrue(StrategyTestFive.has_order_book)

    def test_get_data_with_order_books(self):
        self.algo_app.algorithm.add_strategy(StrategyTestSix)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestSix.has_run)
        self.assertTrue(StrategyTestSix.has_order_books)

    def test_get_data_with_order_book_and_ticker(self):
        self.algo_app.algorithm.add_strategy(StrategyTestEight)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestEight.has_run)
        self.assertTrue(StrategyTestEight.has_order_book)
        self.assertTrue(StrategyTestEight.has_ticker)

    def test_get_data_with_order_books_and_tickers(self):
        self.algo_app.algorithm.add_strategy(StrategyTestSeven)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestSeven.has_run)
        self.assertTrue(StrategyTestSeven.has_order_books)
        self.assertTrue(StrategyTestSeven.has_tickers)

    def test_get_data_with_raw_data(self):
        self.algo_app.algorithm.add_strategy(StrategyTestSix)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestSix.has_run)
        self.assertTrue(StrategyTestSix.has_order_books)

    def test_without_data_provider_registered(self):
        self.algo_app.algorithm.add_strategy(StrategyTestOne)
        self.algo_app.algorithm.add_strategy(StrategyTestTwo)
        self.algo_app.start_algorithm()

        time.sleep(2)

        self.assertTrue(StrategyTestOne.has_run)
        self.assertFalse(StrategyTestTwo.has_run)
