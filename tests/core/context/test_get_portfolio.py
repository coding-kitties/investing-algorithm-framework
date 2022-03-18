from investing_algorithm_framework import Portfolio
from tests.resources import TestBase


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()

    def test(self) -> None:
        self.algo_app.start_algorithm()
        portfolio = self.algo_app.algorithm.get_portfolio()
        self.assertIsNotNone(portfolio)
        self.assertTrue(isinstance(portfolio, Portfolio))

    def test_get_default(self):
        self.algo_app.start_algorithm()
        portfolio = self.algo_app.algorithm.get_portfolio(identifier="default")
        self.assertIsNotNone(portfolio)
        self.assertTrue(isinstance(portfolio, Portfolio))
        self.assertEqual(portfolio.get_identifier(), "default")

    def test_get_sqlite(self):
        self.algo_app.start_algorithm()
        portfolio = self.algo_app.algorithm.get_portfolio(identifier="sqlite")
        self.assertIsNotNone(portfolio)
        self.assertTrue(isinstance(portfolio, Portfolio))
        self.assertEqual(portfolio.get_identifier(), "sqlite")
