from investing_algorithm_framework import TradingTimeUnit, \
    TradingDataTypes, OHLCV
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
            limit=100,
            market="binance"
        )

        ohlcv = data["ohlcv"]
        data = ohlcv.to_dict()
        self.assertIsNotNone(data)
        self.assertEqual(set(data.keys()), set(OHLCV.COLUMNS))
