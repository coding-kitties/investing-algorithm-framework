from investing_algorithm_framework.core.models.snapshots import \
    PortfolioSnapshot
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()
        self.start_algorithm()

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_snapshot_on_creation(self):
        self.assertEqual(1, PortfolioSnapshot.query.count())
        snapshot = PortfolioSnapshot.query.first()
        self.assert_is_portfolio_snapshot(snapshot)

    def test_snapshot_on_to_be_sent_order(self):
        order = self.algo_app.algorithm\
            .create_market_buy_order(
                symbol=self.TARGET_SYMBOL_A, amount_trading_symbol=10
            )

        self.assertEqual(1, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(2, PortfolioSnapshot.query.count())
        latest_portfolio = PortfolioSnapshot.query.order_by(
            PortfolioSnapshot.created_at.desc()
        ).first()

        self.assert_is_portfolio_snapshot(latest_portfolio)

    def test_snapshot_on_pending_order(self):
        order = self.algo_app.algorithm \
            .create_market_buy_order(
                symbol=self.TARGET_SYMBOL_A, amount_trading_symbol=10
            )

        self.assertEqual(1, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, PortfolioSnapshot.query.count())

    def test_snapshot_on_cancel_order(self):
        order = self.algo_app.algorithm \
            .create_market_buy_order(
                symbol=self.TARGET_SYMBOL_A, amount_trading_symbol=10
            )

        self.assertEqual(1, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.cancel()

        self.assertEqual(3, PortfolioSnapshot.query.count())

    def test_snapshot_on_execute_order(self):
        order = self.algo_app.algorithm \
            .create_market_buy_order(
                symbol=self.TARGET_SYMBOL_A, amount_trading_symbol=10
            )

        self.assertEqual(1, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(3, PortfolioSnapshot.query.count())

    def test_snapshot_on_close_order(self):
        order = self.algo_app.algorithm \
            .create_market_buy_order(
                symbol=self.TARGET_SYMBOL_A, amount_trading_symbol=10
            )

        self.assertEqual(1, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_pending()

        self.assertEqual(2, PortfolioSnapshot.query.count())

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(3, PortfolioSnapshot.query.count())

        order = self.algo_app.algorithm \
            .create_market_sell_order(
                symbol=self.TARGET_SYMBOL_A, amount_target_symbol=10
            )

        self.assertEqual(3, PortfolioSnapshot.query.count())

        self.algo_app.algorithm.add_order(order)

        self.assertEqual(3, PortfolioSnapshot.query.count())

        order.set_pending()

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(4, PortfolioSnapshot.query.count())

    def test_snapshot_on_portfolio_updating(self):
        self.assertEqual(1, PortfolioSnapshot.query.count())
        self.algo_app.algorithm.update_unallocated(1000)
        self.assertEqual(2, PortfolioSnapshot.query.count())
