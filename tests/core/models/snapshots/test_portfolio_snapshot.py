from investing_algorithm_framework.core.models.snapshots import \
    SQLLitePortfolioSnapshot
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()
        self.start_algorithm()

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_snapshot_on_creation(self):
        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())
        snapshot = SQLLitePortfolioSnapshot.query.first()
        self.assert_is_portfolio_snapshot(snapshot)

    def test_snapshot_on_to_be_sent_order(self):
        portfolio = self.algo_app.algorithm\
            .get_portfolio_manager()\
            .get_portfolio()

        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        latest_portfolio = SQLLitePortfolioSnapshot.query.order_by(
            SQLLitePortfolioSnapshot.created_at.desc()
        ).first()

        self.assert_is_portfolio_snapshot(latest_portfolio)

    def test_snapshot_on_pending_order(self):
        portfolio = self.algo_app.algorithm\
            .get_portfolio_manager()\
            .get_portfolio()

        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())

        order = self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

    def test_snapshot_on_cancel_order(self):
        portfolio = self.algo_app.algorithm \
            .get_portfolio_manager() \
            .get_portfolio()

        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())

        order = self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.cancel()

        self.assertEqual(3, SQLLitePortfolioSnapshot.query.count())

    def test_snapshot_on_execute_order(self):
        portfolio = self.algo_app.algorithm \
            .get_portfolio_manager() \
            .get_portfolio()

        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())

        order = self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(3, SQLLitePortfolioSnapshot.query.count())

    def test_snapshot_on_close_order(self):
        portfolio = self.algo_app.algorithm \
            .get_portfolio_manager() \
            .get_portfolio()

        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())

        order = self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(3, SQLLitePortfolioSnapshot.query.count())

        order = self.algo_app.algorithm \
            .create_market_sell_order(
                symbol=self.TARGET_SYMBOL_A, amount_target_symbol=1
            )

        self.assertEqual(3, SQLLitePortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(3, SQLLitePortfolioSnapshot.query.count())

        order.set_pending()

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(4, SQLLitePortfolioSnapshot.query.count())

    def test_snapshot_on_portfolio_deposit(self):
        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())
        self.algo_app.algorithm.deposit(1000)
        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())

    def test_snapshot_on_portfolio_withdraw(self):
        self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())
        self.algo_app.algorithm.withdraw(1000)
        self.assertEqual(2, SQLLitePortfolioSnapshot.query.count())
