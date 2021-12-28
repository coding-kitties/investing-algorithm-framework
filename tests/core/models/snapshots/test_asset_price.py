from datetime import datetime

from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.core.models.snapshots import AssetPrice
from tests.resources import TestBase


class TestOrderModel(TestBase):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()
        self.start_algorithm()

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_creation(self):
        asset_price = AssetPrice(
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT",
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            datetime=datetime.utcnow()
        )

        asset_price.save(db)

        self.assertEqual(1, AssetPrice.query.count())
