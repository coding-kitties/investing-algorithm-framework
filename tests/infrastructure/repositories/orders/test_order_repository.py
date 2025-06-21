from investing_algorithm_framework.domain import OrderSide, OrderType, OrderStatus
from investing_algorithm_framework.domain import PortfolioConfiguration, MarketCredential
from tests.resources import TestBase


class TestSQLOrderRepositoryIntegration(TestBase):
    market_credentials = [
        MarketCredential(
            market="BINANCE",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def setUp(self):
        super().setUp()
        self.order_service = self.app.container.order_service()
        self.portfolio_service = self.app.container.portfolio_service()
        self.portfolio = self.portfolio_service.get_all()[0]
        self.repository = self.app.container.order_repository()

    def _create_order(self, **kwargs):
        default_order = {
            "portfolio_id": self.portfolio.id,
            "target_symbol": "BTC",
            "amount": 1,
            "trading_symbol": "EUR",
            "price": 10,
            "order_side": OrderSide.BUY.value,
            "order_type": OrderType.LIMIT.value,
            "status": OrderStatus.OPEN.value,
        }
        default_order.update(kwargs)
        order = self.order_service.create(default_order)

        if "external_id" in kwargs:
            order = self.order_service.update(
                order.id,
                {"external_id": kwargs["external_id"]}
            )

        if "status" in kwargs:
            order = self.order_service.update(
                order.id,
                {"status": kwargs["status"]}
            )

        return order

    def test_filter_by_id(self):
        order = self._create_order()
        result = self.repository.get_all({"id": order.id})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, order.id)

    def test_filter_by_external_id(self):
        self._create_order(external_id="custom_ext_id_123")
        result = self.repository.get_all({"external_id": "custom_ext_id_123"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].external_id, "custom_ext_id_123")

    def test_filter_by_order_type_and_status(self):
        order = self._create_order(order_type="LIMIT", status="CLOSED")
        result = self.repository.get_all({
            "order_type": "LIMIT",
            "status": "CLOSED"
        })
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, OrderStatus.CLOSED.value)

    def test_filter_by_portfolio_id(self):
        self._create_order()
        result = self.repository.get_all({"portfolio_id": self.portfolio.id})
        self.assertEqual(len(result), 1)

    def test_filter_by_price_and_amount(self):
        self._create_order(price=99.99, amount=3.0)
        result = self.repository.get_all({"price": 99.99, "amount": 3.0})
        self.assertEqual(len(result), 1)

    def test_filter_by_target_symbol_and_trading_symbol(self):
        order = self._create_order(target_symbol="ETH", trading_symbol="EUR")
        result = self.repository.get_all({
            "target_symbol": "ETH",
            "trading_symbol": "EUR"
        })
        self.assertEqual(len(result), 1)

    def test_order_by_created_at_asc(self):
        self._create_order()
        self._create_order()
        results = self.repository.get_all({
            "order_by_created_at_asc": True
        })
        self.assertLessEqual(results[0].created_at, results[1].created_at)

    def test_order_by_created_at_desc(self):
        self._create_order()
        self._create_order()
        results = self.repository.get_all({
            "order_by_created_at_asc": False
        })
        self.assertGreaterEqual(results[0].created_at, results[1].created_at)
