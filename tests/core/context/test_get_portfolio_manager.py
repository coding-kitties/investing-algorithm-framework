from tests.resources import TestBase


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()

    def test(self) -> None:
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        self.assertIsNotNone(portfolio_manager)

    def test_default(self) -> None:
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager("default")
        self.assertIsNotNone(portfolio_manager)

    def test_sqlite(self) -> None:
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager("sqlite")
        self.assertIsNotNone(portfolio_manager)
