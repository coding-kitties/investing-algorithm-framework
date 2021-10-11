from tests.resources import TestBase, random_string
from investing_algorithm_framework import BinanceOrderExecutor
from investing_algorithm_framework.core.exceptions import OperationalException


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_order_executor(BinanceOrderExecutor())

    def test_initialize(self):
        binance_order_executor = self.algo_app.algorithm\
            .get_order_executor("BINANCE")

        with self.assertRaises(OperationalException) as exc_info:
            binance_order_executor.initialize(self.algo_app.algorithm)

        self.algo_app.algorithm.config.set("API_KEY", random_string(10))
        self.algo_app.algorithm.config.set("SECRET_KEY", random_string(10))

        binance_order_executor.initialize(self.algo_app.algorithm)

    def test_retrieve(self):
        order_executor = self.algo_app.algorithm.get_order_executor("BINANCE")
        self.assertIsNotNone(order_executor)
        self.assertEqual(order_executor.identifier, "BINANCE")
