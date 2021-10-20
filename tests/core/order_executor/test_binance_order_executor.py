from investing_algorithm_framework import BinanceOrderExecutor
from investing_algorithm_framework.configuration.constants import BINANCE
from tests.resources import TestBase


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_order_executor(BinanceOrderExecutor())

    def test_retrieve(self):
        order_executor = self.algo_app.algorithm.get_order_executor(BINANCE)
        self.assertIsNotNone(order_executor)
        self.assertEqual(order_executor.identifier, BINANCE)
