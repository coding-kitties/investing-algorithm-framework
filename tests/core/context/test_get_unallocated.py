from investing_algorithm_framework import Position
from tests.resources import TestBase


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()

    def test(self) -> None:
        self.algo_app.start_algorithm()
        position = self.algo_app.algorithm.get_unallocated()
        self.assertIsNotNone(position)
        self.assertTrue(isinstance(position, Position))
        self.assertEqual("USDT", position.get_symbol())

    def test_get_default(self):
        self.algo_app.start_algorithm()
        position = self.algo_app.algorithm\
            .get_unallocated(identifier="default")
        self.assertIsNotNone(position)
        self.assertTrue(isinstance(position, Position))
        self.assertEqual("USDT", position.get_symbol())

    def test_get_sqlite(self):
        self.algo_app.start_algorithm()
        position = self.algo_app.algorithm\
            .get_unallocated(identifier="sqlite")
        self.assertIsNotNone(position)
        self.assertTrue(isinstance(position, Position))
        self.assertEqual("USDT", position.get_symbol())
