from tests.resources import TestBase


class Test(TestBase):

    def test_retrieve(self):
        order_executor = self.algo_app.algorithm.get_order_executor()
        self.assertIsNotNone(order_executor)
