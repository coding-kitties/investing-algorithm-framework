from tests.resources import TestBase
from investing_algorithm_framework.core.workers import Strategy
from investing_algorithm_framework import TradingDataTypes, TradingTimeUnit, \
    AlgorithmContext
from investing_algorithm_framework.configuration.constants import \
    RESOURCE_DIRECTORY


class StrategyOne(Strategy):

    has_ohlcv_data = False
    has_orders = False
    has_positions = False
    has_unallocated = False

    def __init__(self):
        super(StrategyOne, self).__init__(
            worker_id="strategy_one",
            trading_symbol="usdt",
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbol="BTC",
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
        ohclvs=None,
        **kwargs
    ):
        if ohlcv is not None:
            StrategyOne.has_ohlcv_data = True

        orders = context.get_orders("TEST_ONE")

        if len(orders) > 0:
            StrategyOne.has_orders = True

        positions = context.get_positions("TEST_ONE")

        if len(positions) > 0:
            StrategyOne.has_positions = True

        unallocated = context.get_unallocated("TEST_ONE")

        if unallocated.get_amount() > 0:
            StrategyOne.has_unallocated = True


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
            worker_id="strategy_one",
            trading_symbol="usdt",
            trading_data_type=TradingDataTypes.OHLCV,
            target_symbol="BTC",
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
        ohclvs=None,
        **kwargs
    ):
        if ohlcv is not None:
            StrategyOne.has_ohlcv_data = True

        orders = context.get_orders("TEST_ONE")

        if len(orders) > 0:
            StrategyOne.has_orders = True

        positions = context.get_positions("TEST_ONE")

        if len(positions) > 0:
            StrategyOne.has_positions = True

        unallocated = context.get_unallocated("TEST_ONE")

        if unallocated.get_amount() > 0:
            StrategyOne.has_unallocated = True

class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_strategy(StrategyOne())

    def test_with_strategy_specification(self):
        payload = {
            "ACTION": "RUN_STRATEGY",
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
        self.assertTrue(StrategyOne.has_ohlcv_data)
        self.assertTrue(StrategyOne.has_orders)
        self.assertTrue(StrategyOne.has_positions)
        self.assertTrue(StrategyOne.has_unallocated)

    def test_with_no_strategy_specification(self):
        payload = {
            "ACTION": "RUN_STRATEGY",
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
        self.assertTrue(StrategyOne.has_ohlcv_data)
        self.assertTrue(StrategyOne.has_orders)
        self.assertTrue(StrategyOne.has_positions)
        self.assertTrue(StrategyOne.has_unallocated)
