from datetime import timedelta, datetime

from investing_algorithm_framework.core.models import Portfolio, \
    PortfolioSnapshot, PerformanceMetric, OrderSide, TimeFrame
from investing_algorithm_framework.core.performance import \
    PerformanceService
from tests.resources import TestBase


class TestClass(TestBase):

    def setUp(self) -> None:
        super(TestClass, self).setUp()
        self.start_algorithm()

    def test_delta(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(minutes=30)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.DELTA,
            time_frame=TimeFrame.ONE_HOUR
        )

        print(data)

    def test_overall_performance_one_hour(self):
        portfolio = Portfolio.query.first()

        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=200)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() + timedelta(),
            side=OrderSide.BUY.value,
            execution_datetime=None,
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow(),
            side=OrderSide.BUY.value,
            execution_datetime=None,
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow(),
            side=OrderSide.BUY.value,
            execution_datetime=None,
            executed=True,
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # With no price increases value should be 0
        for point in data:
            self.assertEqual(0, point["value"])

    def test_profit_realized_unrealized_one_hour_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(minutes=30)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.04, data_point["value"], max_difference=0.01
                )

    def test_profit_realized_unrealized_one_hour_withdrawel(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        withdraw_date = datetime.utcnow() - timedelta(minutes=45)

        portfolio.withdraw(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            self.assertEqual(0, data_point["value"])

    def test_profit_realized_unrealized_one_hour_withdrawel_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        withdraw_date = datetime.utcnow() - timedelta(minutes=45)

        portfolio.withdraw(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(minutes=30)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.08, data_point["value"], max_difference=0.01
                )

    def test_profit_realized_unrealized_one_hour_deposit(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        withdraw_date = datetime.utcnow() - timedelta(minutes=45)

        portfolio.deposit(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            self.assertEqual(0, data_point["value"])

    def test_profit_realized_unrealized_one_hour_deposit_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=61)

        withdraw_date = datetime.utcnow() - timedelta(minutes=45)

        portfolio.deposit(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=42),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=41),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=datetime.utcnow() - timedelta(minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=datetime.utcnow() - timedelta(minutes=38),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(minutes=30)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.026, data_point["value"], max_difference=0.01
                )

    def test_overall_performance_one_day(self):
        portfolio = Portfolio.query.first()

        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=10),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=11),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=40),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=39),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=38),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5, minutes=38),
            executed=True,
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_DAY
        )

        # With no price increases value should be 0
        for point in data:
            self.assertEqual(0, point["value"])

    def test_profit_realized_unrealized_one_day_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(hours=4)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_DAY
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.04, data_point["value"], max_difference=0.01
                )

    def test_profit_realized_unrealized_one_day_withdrawel(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        withdraw_date = datetime.utcnow() - timedelta(hours=11)

        portfolio.withdraw(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            self.assertEqual(0, data_point["value"])

    def test_profit_realized_unrealized_one_day_withdrawel_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        withdraw_date = datetime.utcnow() - timedelta(hours=11)

        portfolio.withdraw(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(hours=6)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_DAY
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.08, data_point["value"], max_difference=0.01
                )

    def test_profit_realized_unrealized_one_day_deposit(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        withdraw_date = datetime.utcnow() - timedelta(hours=11)

        portfolio.deposit(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(hours=6)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_HOUR
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            self.assertEqual(0, data_point["value"])

    def test_profit_realized_unrealized_one_day_deposit_updated(self):
        portfolio = Portfolio.query.first()
        first_snapshot = PortfolioSnapshot.query.first()

        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        # Update datetime of creation of snapshot before range
        # Then we have at least one snapshot before the range
        first_snapshot.created_at = datetime.utcnow() - timedelta(days=2)

        withdraw_date = datetime.utcnow() - timedelta(hours=11)

        portfolio.deposit(500, creation_datetime=withdraw_date)

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_B,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_C,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_C).price,
            creation_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            side=OrderSide.BUY.value,
            execution_datetime=
            datetime.utcnow() - timedelta(hours=5) - timedelta(minutes=50),
            executed=True,
        )

        update_date = datetime.utcnow() - timedelta(hours=6)

        self.update_price(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE * 1.5,
            date=update_date
        )

        self.update_price(
            self.TARGET_SYMBOL_C,
            self.BASE_SYMBOL_C_PRICE * 1.5,
            date=update_date
        )

        data = PerformanceService.of_metric(
            portfolio,
            metric=PerformanceMetric.OVERALL_PERFORMANCE,
            time_frame=TimeFrame.ONE_DAY
        )

        # before update date value should be 0 after update date value
        # should be 25
        for data_point in data:
            if data_point["datetime"] < update_date:
                self.assertEqual(0, data_point["value"])
            else:
                self.assert_almost_equal(
                    0.026, data_point["value"], max_difference=0.01
                )
