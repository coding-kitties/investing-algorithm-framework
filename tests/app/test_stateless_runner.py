from investing_algorithm_framework import TradingDataTypes, TradingTimeUnit, \
    AlgorithmContext
from investing_algorithm_framework.core.workers import Strategy
from investing_algorithm_framework.app.stateless.action_handlers import Action
from tests.resources import TestBase


class StrategyOne(Strategy):
    has_ohlcv_data = False
    has_ohlcvs_data = False
    has_ticker_data = False
    has_tickers_data = False
    has_order_book_data = False
    has_order_books_data = False
    has_orders = False
    has_positions = False
    has_unallocated = False

    def __init__(self):
        super(StrategyOne, self).__init__(
            worker_id="strategy_one",
            trading_symbol="usdt",
            trading_data_types=[
                TradingDataTypes.OHLCV,
                TradingDataTypes.TICKER,
                TradingDataTypes.ORDER_BOOK
            ],
            target_symbols=["BTC", "DOT"],
            market="BINANCE",
            limit=100,
            trading_time_unit=TradingTimeUnit.ONE_DAY
        )

    def apply_strategy(
        self,
        context: AlgorithmContext,
        ticker=None,
        tickers=None,
        order_book=None,
        order_books=None,
        ohlcv=None,
        ohlcvs=None,
        **kwargs
    ):

        if ohlcv is not None:
            StrategyOne.has_ohlcv_data = True

        if ohlcvs is not None:
            StrategyOne.has_ohlcvs_data = True

        orders = context.get_orders("TEST_ONE")

        if len(orders) > 0:
            StrategyOne.has_orders = True

        positions = context.get_positions("TEST_ONE")

        if len(positions) > 0:
            StrategyOne.has_positions = True

        unallocated = context.get_unallocated("TEST_ONE")

        if unallocated.get_amount() > 0:
            StrategyOne.has_unallocated = True

    @staticmethod
    def reset():
        StrategyOne.has_ohlcv_data = False
        StrategyOne.has_ohlcvs_data = False
        StrategyOne.has_ticker_data = False
        StrategyOne.has_tickers_data = False
        StrategyOne.has_order_book_data = False
        StrategyOne.has_order_books_data = False
        StrategyOne.has_orders = False
        StrategyOne.has_positions = False
        StrategyOne.has_unallocated = False


class StrategyTwo(Strategy):

    has_ohlcv_data = False
    has_ohlcvs_data = False
    has_ticker_data = False
    has_tickers_data = False
    has_order_book_data = False
    has_order_books_data = False
    has_orders = False
    has_positions = False
    has_unallocated = False

    def __init__(self):
        super(StrategyTwo, self).__init__(
            worker_id="strategy_two",
            trading_symbol="usdt",
            trading_data_type=TradingDataTypes.TICKER,
            target_symbol="BTC",
            market="BINANCE",
        )

    def apply_strategy(
        self,
        context: AlgorithmContext,
        ticker=None,
        tickers=None,
        order_book=None,
        order_books=None,
        ohlcv=None,
        ohlcvs=None,
        **kwargs
    ):
        if ticker is not None:
            StrategyTwo.has_ticker_data = True

        orders = context.get_orders("TEST_ONE")

        if len(orders) > 0:
            StrategyTwo.has_orders = True

        positions = context.get_positions("TEST_ONE")

        if len(positions) > 0:
            StrategyTwo.has_positions = True

        unallocated = context.get_unallocated("TEST_ONE")

        if unallocated.get_amount() > 0:
            StrategyTwo.has_unallocated = True

    @staticmethod
    def reset():
        StrategyTwo.has_ohlcv_data = False
        StrategyTwo.has_ohlcvs_data = False
        StrategyTwo.has_ticker_data = False
        StrategyTwo.has_tickers_data = False
        StrategyTwo.has_order_book_data = False
        StrategyTwo.has_order_books_data = False
        StrategyTwo.has_orders = False
        StrategyTwo.has_positions = False
        StrategyTwo.has_unallocated = False


class StrategyThree(Strategy):

    has_ohlcv_data = False
    has_ohlcvs_data = False
    has_ticker_data = False
    has_tickers_data = False
    has_order_book_data = False
    has_order_books_data = False
    has_orders = False
    has_positions = False
    has_unallocated = False

    def __init__(self):
        super(StrategyThree, self).__init__(
            worker_id="strategy_three",
            trading_symbol="usdt",
            trading_data_types=[
                TradingDataTypes.TICKER, TradingDataTypes.ORDER_BOOK
            ],
            target_symbols=["BTC", "DOT"],
            market="BINANCE",
        )

    def apply_strategy(
        self,
        context: AlgorithmContext,
        ticker=None,
        tickers=None,
        order_book=None,
        order_books=None,
        ohlcv=None,
        ohlcvs=None,
        **kwargs
    ):

        if ticker is not None:
            StrategyThree.has_ticker_data = True

        if tickers is not None:
            StrategyThree.has_tickers_data = True

        if order_book is not None:
            StrategyThree.has_order_book_data = True

        if order_books is not None:
            StrategyThree.has_order_books_data = True

        orders = context.get_orders("TEST_ONE")

        if len(orders) > 0:
            StrategyThree.has_orders = True

        positions = context.get_positions("TEST_ONE")

        if len(positions) > 0:
            StrategyThree.has_positions = True

        unallocated = context.get_unallocated("TEST_ONE")

        if unallocated.get_amount() > 0:
            StrategyThree.has_unallocated = True

    @staticmethod
    def reset():
        StrategyThree.has_ohlcv_data = False
        StrategyThree.has_ohlcvs_data = False
        StrategyThree.has_ticker_data = False
        StrategyThree.has_tickers_data = False
        StrategyThree.has_order_book_data = False
        StrategyThree.has_order_books_data = False
        StrategyThree.has_orders = False
        StrategyThree.has_positions = False
        StrategyThree.has_unallocated = False


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_strategy(StrategyOne())
        self.algo_app.algorithm.add_strategy(StrategyTwo())
        self.algo_app.algorithm.add_strategy(StrategyThree())
        StrategyOne.reset()
        StrategyTwo.reset()
        StrategyThree.reset()

    def test_with_strategy_specification(self):
        payload = {
            "ACTION": Action.RUN_STRATEGY,
            "STRATEGIES": [
                "strategy_one"
            ],
            "PORTFOLIOS": {
                "TEST_ONE": {
                    "trading_symbol": "USDT",
                    "market": "BINANCE",
                    "positions": [
                        {"symbol": "USDT", "amount": 10000},
                        {"symbol": "DOT", "amount": 40},
                        {"symbol": "BTC", "amount": 0.04},
                    ],
                    "orders": [
                        {
                            "reference_id": 1,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 2,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 3,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        }
                    ]
                }
            }
        }
        self.algo_app.start(stateless=True, payload=payload)
        self.assertTrue(StrategyOne.has_ohlcvs_data)
        self.assertFalse(StrategyOne.has_ohlcv_data)
        self.assertTrue(StrategyOne.has_orders)
        self.assertTrue(StrategyOne.has_positions)
        self.assertTrue(StrategyOne.has_unallocated)

        self.assertFalse(StrategyTwo.has_ticker_data)

    def test_with_no_strategy_specification(self):
        payload = {
            "ACTION": Action.RUN_STRATEGY,
            "PORTFOLIOS": {
                "TEST_ONE": {
                    "trading_symbol": "USDT",
                    "market": "BINANCE",
                    "positions": [
                        {"symbol": "USDT", "amount": 10000},
                        {"symbol": "DOT", "amount": 40},
                        {"symbol": "BTC", "amount": 0.04},
                    ],
                    "orders": [
                        {
                            "reference_id": 1,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 2,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 3,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        }
                    ]
                }
            }
        }
        self.algo_app.start(stateless=True, payload=payload)
        self.assertTrue(StrategyOne.has_ohlcvs_data)
        self.assertFalse(StrategyOne.has_ohlcv_data)
        self.assertTrue(StrategyOne.has_orders)
        self.assertTrue(StrategyOne.has_positions)
        self.assertTrue(StrategyOne.has_unallocated)

        self.assertTrue(StrategyTwo.has_ticker_data)
        self.assertTrue(StrategyTwo.has_orders)
        self.assertTrue(StrategyTwo.has_unallocated)
        self.assertTrue(StrategyTwo.has_positions)

    def test_with_all_strategy_specifications(self):
        payload = {
            "ACTION": Action.RUN_STRATEGY,
            "STRATEGIES": [
                "strategy_one",
                "strategy_two",
                "strategy_three"
            ],
            "PORTFOLIOS": {
                "TEST_ONE": {
                    "trading_symbol": "USDT",
                    "market": "BINANCE",
                    "positions": [
                        {"symbol": "USDT", "amount": 10000},
                        {"symbol": "DOT", "amount": 40},
                        {"symbol": "BTC", "amount": 0.04},
                    ],
                    "orders": [
                        {
                            "reference_id": 1,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 2,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        },
                        {
                            "reference_id": 3,
                            "target_symbol": "DOT",
                            "trading_symbol": "USDT",
                            "amount_target_symbol": 40,
                            "status": "PENDING",
                            "price": 10,
                            "type": "LIMIT",
                            "side": "BUY"
                        }
                    ]
                }
            }
        }
        self.algo_app.start(stateless=True, payload=payload)
        self.assertTrue(StrategyOne.has_ohlcvs_data)
        self.assertFalse(StrategyOne.has_ohlcv_data)
        self.assertTrue(StrategyOne.has_orders)
        self.assertTrue(StrategyOne.has_positions)
        self.assertTrue(StrategyOne.has_unallocated)

        self.assertTrue(StrategyTwo.has_ticker_data)
        self.assertTrue(StrategyTwo.has_orders)
        self.assertTrue(StrategyTwo.has_unallocated)
        self.assertTrue(StrategyTwo.has_positions)

        self.assertTrue(StrategyThree.has_tickers_data)
        self.assertTrue(StrategyThree.has_order_books_data)
        self.assertTrue(StrategyThree.has_unallocated)
        self.assertTrue(StrategyThree.has_positions)

    def test_check_online(self):
        payload = {"action": Action.CHECK_ONLINE.value}
        response = self.algo_app.start(stateless=True, payload=payload)
        self.assertEqual(response["statusCode"], 200)

        payload = {"ACTION": Action.CHECK_ONLINE.value}
        response = self.algo_app.start(stateless=True, payload=payload)
        self.assertEqual(response["statusCode"], 200)
