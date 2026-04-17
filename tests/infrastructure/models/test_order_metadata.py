"""
Tests for SQLOrder.metadata persistence (metadata_json column).
"""
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from investing_algorithm_framework.domain import OrderSide, OrderType, \
    OrderStatus
from investing_algorithm_framework.infrastructure.models import SQLOrder
from tests.resources import TestBase


class TestSQLOrderMetadata(TestBase):
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

    def test_creation_with_metadata(self):
        """SQLOrder created with metadata dict stores it in metadata_json."""
        order = SQLOrder(
            amount=1.0,
            price=100.0,
            order_side="BUY",
            order_type="LIMIT",
            status="OPEN",
            target_symbol="BTC",
            trading_symbol="EUR",
            metadata={"order_reason": "buy_signal"},
        )
        self.assertEqual(order.metadata, {"order_reason": "buy_signal"})
        self.assertIsNotNone(order.metadata_json)
        self.assertIn("buy_signal", order.metadata_json)

    def test_creation_without_metadata(self):
        """SQLOrder created without metadata has empty dict and None json."""
        order = SQLOrder(
            amount=1.0,
            price=100.0,
            order_side="BUY",
            order_type="LIMIT",
            status="OPEN",
            target_symbol="BTC",
            trading_symbol="EUR",
        )
        self.assertEqual(order.metadata, {})
        self.assertIsNone(order.metadata_json)

    def test_to_dict_includes_metadata(self):
        """to_dict() output includes metadata."""
        order = SQLOrder(
            amount=1.0,
            price=100.0,
            order_side="BUY",
            order_type="LIMIT",
            status="OPEN",
            target_symbol="BTC",
            trading_symbol="EUR",
            metadata={"order_reason": "stop_loss"},
        )
        d = order.to_dict()
        self.assertIn("metadata", d)
        self.assertEqual(d["metadata"]["order_reason"], "stop_loss")


class TestSQLOrderMetadataDBPersistence(TestBase):
    """Tests that metadata survives a write→read DB round-trip."""
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

    def _create_order(self, metadata=None):
        data = {
            "portfolio_id": self.portfolio.id,
            "target_symbol": "BTC",
            "amount": 1,
            "trading_symbol": "EUR",
            "price": 10,
            "order_side": OrderSide.BUY.value,
            "order_type": OrderType.LIMIT.value,
            "status": OrderStatus.OPEN.value,
        }
        if metadata is not None:
            data["metadata"] = metadata
        return self.order_service.create(data)

    def test_metadata_persists_through_db(self):
        """Metadata written to DB can be read back correctly."""
        order = self._create_order(
            metadata={"order_reason": "buy_signal"}
        )
        retrieved = self.repository.get(order.id)
        self.assertEqual(
            retrieved.metadata.get("order_reason"), "buy_signal"
        )

    def test_metadata_with_multiple_keys_persists(self):
        order = self._create_order(
            metadata={
                "order_reason": "stop_loss",
                "stop_loss_id": 42,
            }
        )
        retrieved = self.repository.get(order.id)
        self.assertEqual(retrieved.metadata["order_reason"], "stop_loss")
        self.assertEqual(retrieved.metadata["stop_loss_id"], 42)

    def test_no_metadata_returns_empty_dict(self):
        """Order created without metadata returns {} when read back."""
        order = self._create_order()
        retrieved = self.repository.get(order.id)
        self.assertEqual(retrieved.metadata, {})

    def test_update_metadata(self):
        """Metadata can be updated via the update method."""
        order = self._create_order(
            metadata={"order_reason": "buy_signal"}
        )
        self.repository.update(
            order.id,
            {"metadata": {"order_reason": "scale_in"}}
        )
        retrieved = self.repository.get(order.id)
        self.assertEqual(
            retrieved.metadata.get("order_reason"), "scale_in"
        )

    def test_all_order_reasons_persist(self):
        """All expected order_reason values round-trip through DB."""
        reasons = [
            "buy_signal", "sell_signal", "scale_in",
            "scale_out", "stop_loss", "take_profit",
        ]
        for reason in reasons:
            order = self._create_order(
                metadata={"order_reason": reason}
            )
            retrieved = self.repository.get(order.id)
            self.assertEqual(
                retrieved.metadata.get("order_reason"), reason,
                f"Round-trip failed for order_reason={reason}",
            )
