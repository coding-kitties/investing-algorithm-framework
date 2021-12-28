import json
from datetime import datetime, timedelta

from investing_algorithm_framework.core.models import OrderSide, Portfolio, \
    PortfolioSnapshot
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import portfolio_serialization_dict


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

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

    def test_retrieve(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        response = self.client.get(
            f"/api/portfolios/{portfolio_manager.get_portfolio().identifier}"
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            portfolio_serialization_dict, set(data.keys())
        )

    def test_retrieve_default(self):
        response = self.client.get(
            f"/api/portfolios/default"
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            portfolio_serialization_dict, set(data.keys())
        )
