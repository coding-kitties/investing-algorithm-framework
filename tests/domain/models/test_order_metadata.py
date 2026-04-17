"""
Tests for Order.metadata on the domain model.
"""
from unittest import TestCase

from investing_algorithm_framework.domain import Order, OrderType, \
    OrderSide, OrderStatus


class TestOrderMetadata(TestCase):

    def test_metadata_default_is_empty_dict(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="USD",
        )
        self.assertEqual(order.metadata, {})

    def test_metadata_none_becomes_empty_dict(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="USD",
            metadata=None,
        )
        self.assertEqual(order.metadata, {})

    def test_metadata_with_order_reason(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="USD",
            metadata={"order_reason": "buy_signal"},
        )
        self.assertEqual(order.metadata, {"order_reason": "buy_signal"})
        self.assertEqual(order.metadata["order_reason"], "buy_signal")

    def test_metadata_with_multiple_keys(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.SELL,
            amount=0.5,
            target_symbol="ETH",
            trading_symbol="USD",
            metadata={
                "order_reason": "stop_loss",
                "triggered_at_price": 1800.0,
            },
        )
        self.assertEqual(order.metadata["order_reason"], "stop_loss")
        self.assertEqual(order.metadata["triggered_at_price"], 1800.0)

    def test_metadata_in_to_dict(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="USD",
            metadata={"order_reason": "scale_in"},
        )
        d = order.to_dict()
        self.assertIn("metadata", d)
        self.assertEqual(d["metadata"]["order_reason"], "scale_in")

    def test_metadata_empty_in_to_dict(self):
        order = Order(
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            amount=1.0,
            target_symbol="BTC",
            trading_symbol="USD",
        )
        d = order.to_dict()
        self.assertEqual(d["metadata"], {})

    def test_all_order_reason_values(self):
        """Verify all expected order_reason values work."""
        reasons = [
            "buy_signal", "sell_signal", "scale_in",
            "scale_out", "stop_loss", "take_profit",
        ]
        for reason in reasons:
            order = Order(
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
                amount=1.0,
                target_symbol="BTC",
                trading_symbol="USD",
                metadata={"order_reason": reason},
            )
            self.assertEqual(
                order.metadata["order_reason"], reason,
                f"Failed for order_reason={reason}",
            )
