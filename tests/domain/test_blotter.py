import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from investing_algorithm_framework.domain.blotter import (
    Blotter, SimulationBlotter, Transaction,
    SlippageModel, NoSlippage, PercentageSlippage, FixedSlippage,
    CommissionModel, NoCommission, PercentageCommission, FixedCommission,
)


class TestNoSlippage(unittest.TestCase):

    def test_buy_no_slippage(self):
        model = NoSlippage()
        self.assertEqual(model.calculate_slippage(100.0, "BUY"), 100.0)

    def test_sell_no_slippage(self):
        model = NoSlippage()
        self.assertEqual(model.calculate_slippage(100.0, "SELL"), 100.0)


class TestPercentageSlippage(unittest.TestCase):

    def test_buy_slippage_increases_price(self):
        model = PercentageSlippage(percentage=0.01)
        result = model.calculate_slippage(100.0, "BUY")
        self.assertAlmostEqual(result, 101.0)

    def test_sell_slippage_decreases_price(self):
        model = PercentageSlippage(percentage=0.01)
        result = model.calculate_slippage(100.0, "SELL")
        self.assertAlmostEqual(result, 99.0)

    def test_default_percentage(self):
        model = PercentageSlippage()
        self.assertEqual(model.percentage, 0.001)

    def test_small_slippage(self):
        model = PercentageSlippage(percentage=0.001)
        result = model.calculate_slippage(50000.0, "BUY")
        self.assertAlmostEqual(result, 50050.0)


class TestFixedSlippage(unittest.TestCase):

    def test_buy_slippage_adds_fixed_amount(self):
        model = FixedSlippage(amount=0.50)
        result = model.calculate_slippage(100.0, "BUY")
        self.assertAlmostEqual(result, 100.50)

    def test_sell_slippage_subtracts_fixed_amount(self):
        model = FixedSlippage(amount=0.50)
        result = model.calculate_slippage(100.0, "SELL")
        self.assertAlmostEqual(result, 99.50)

    def test_default_amount(self):
        model = FixedSlippage()
        self.assertEqual(model.amount, 0.01)


class TestNoCommission(unittest.TestCase):

    def test_zero_commission(self):
        model = NoCommission()
        result = model.calculate_commission(100.0, 10.0, "BUY")
        self.assertEqual(result, 0.0)


class TestPercentageCommission(unittest.TestCase):

    def test_commission_calculation(self):
        model = PercentageCommission(percentage=0.001)
        # 100 * 10 * 0.001 = 1.0
        result = model.calculate_commission(100.0, 10.0, "BUY")
        self.assertAlmostEqual(result, 1.0)

    def test_default_percentage(self):
        model = PercentageCommission()
        self.assertEqual(model.percentage, 0.001)

    def test_sell_commission(self):
        model = PercentageCommission(percentage=0.002)
        # 50 * 5 * 0.002 = 0.5
        result = model.calculate_commission(50.0, 5.0, "SELL")
        self.assertAlmostEqual(result, 0.5)


class TestFixedCommission(unittest.TestCase):

    def test_fixed_commission(self):
        model = FixedCommission(amount=5.0)
        result = model.calculate_commission(100.0, 10.0, "BUY")
        self.assertEqual(result, 5.0)

    def test_default_amount(self):
        model = FixedCommission()
        self.assertEqual(model.amount, 1.0)


class TestTransaction(unittest.TestCase):

    def test_transaction_creation(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=45000.0,
            amount=0.1,
            cost=4500.0,
            commission=4.5,
            slippage=45.0,
            timestamp=ts,
        )
        self.assertEqual(tx.order_id, 1)
        self.assertEqual(tx.symbol, "BTC/EUR")
        self.assertEqual(tx.order_side, "BUY")
        self.assertEqual(tx.price, 45000.0)
        self.assertEqual(tx.amount, 0.1)
        self.assertEqual(tx.cost, 4500.0)
        self.assertEqual(tx.commission, 4.5)
        self.assertEqual(tx.slippage, 45.0)
        self.assertEqual(tx.timestamp, ts)

    def test_transaction_defaults(self):
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=100.0,
            amount=1.0,
            cost=100.0,
        )
        self.assertEqual(tx.commission, 0.0)
        self.assertEqual(tx.slippage, 0.0)
        self.assertIsNotNone(tx.timestamp)

    def test_to_dict(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=100.0,
            amount=1.0,
            cost=100.0,
            commission=0.1,
            slippage=0.5,
            timestamp=ts,
        )
        d = tx.to_dict()
        self.assertEqual(d["order_id"], 1)
        self.assertEqual(d["symbol"], "BTC/EUR")
        self.assertEqual(d["price"], 100.0)
        self.assertEqual(d["commission"], 0.1)
        self.assertEqual(d["slippage"], 0.5)
        self.assertIn("2024-01-01", d["timestamp"])

    def test_repr(self):
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=100.0,
            amount=1.0,
            cost=100.0,
        )
        r = repr(tx)
        self.assertIn("BTC/EUR", r)
        self.assertIn("order_id=1", r)


class ConcreteBlotter(Blotter):
    """Minimal concrete implementation for testing."""

    def place_order(self, order_data, context):
        return context.create_limit_order(
            target_symbol=order_data["target_symbol"],
            price=order_data["price"],
            order_side=order_data["order_side"],
            amount=order_data.get("amount"),
        )

    def cancel_order(self, order_id, context):
        return context.order_service.update(
            order_id, {"status": "CANCELED"}
        )


class TestBlotter(unittest.TestCase):

    def test_is_abstract(self):
        with self.assertRaises(TypeError):
            Blotter()

    def test_concrete_blotter(self):
        blotter = ConcreteBlotter()
        self.assertIsNotNone(blotter)
        self.assertEqual(blotter.get_transactions(), [])

    def test_config_property(self):
        blotter = ConcreteBlotter()
        self.assertIsNone(blotter.config)
        blotter.config = {"key": "value"}
        self.assertEqual(blotter.config["key"], "value")

    def test_record_transaction(self):
        blotter = ConcreteBlotter()
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=100.0,
            amount=1.0,
            cost=100.0,
        )
        blotter.record_transaction(tx)
        self.assertEqual(len(blotter.get_transactions()), 1)
        self.assertEqual(blotter.get_transactions()[0].order_id, 1)

    def test_clear_transactions(self):
        blotter = ConcreteBlotter()
        tx = Transaction(
            order_id=1,
            symbol="BTC/EUR",
            order_side="BUY",
            price=100.0,
            amount=1.0,
            cost=100.0,
        )
        blotter.record_transaction(tx)
        self.assertEqual(len(blotter.get_transactions()), 1)
        blotter.clear_transactions()
        self.assertEqual(len(blotter.get_transactions()), 0)

    def test_batch_order_calls_place_order(self):
        blotter = ConcreteBlotter()
        context = MagicMock()

        mock_order_1 = MagicMock()
        mock_order_2 = MagicMock()
        context.create_limit_order.side_effect = [
            mock_order_1, mock_order_2
        ]

        orders = [
            {
                "target_symbol": "BTC",
                "price": 45000,
                "order_side": "BUY",
                "amount": 0.1,
            },
            {
                "target_symbol": "ETH",
                "price": 3000,
                "order_side": "BUY",
                "amount": 1.0,
            },
        ]

        results = blotter.batch_order(orders, context)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], mock_order_1)
        self.assertEqual(results[1], mock_order_2)
        self.assertEqual(context.create_limit_order.call_count, 2)

    def test_get_open_orders_delegates_to_context(self):
        blotter = ConcreteBlotter()
        context = MagicMock()
        context.get_open_orders.return_value = ["order1", "order2"]

        result = blotter.get_open_orders(context, target_symbol="BTC")
        context.get_open_orders.assert_called_once_with(
            target_symbol="BTC"
        )
        self.assertEqual(result, ["order1", "order2"])

    def test_prune_orders_does_not_raise(self):
        blotter = ConcreteBlotter()
        context = MagicMock()
        blotter.prune_orders(context)


class TestSimulationBlotter(unittest.TestCase):

    def test_default_models(self):
        blotter = SimulationBlotter()
        self.assertIsInstance(blotter.slippage_model, NoSlippage)
        self.assertIsInstance(blotter.commission_model, NoCommission)

    def test_custom_models(self):
        blotter = SimulationBlotter(
            slippage_model=PercentageSlippage(0.01),
            commission_model=PercentageCommission(0.002),
        )
        self.assertIsInstance(blotter.slippage_model, PercentageSlippage)
        self.assertEqual(blotter.slippage_model.percentage, 0.01)
        self.assertIsInstance(
            blotter.commission_model, PercentageCommission
        )
        self.assertEqual(blotter.commission_model.percentage, 0.002)

    def test_place_limit_order(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 45000.0
        mock_order.get_amount.return_value = 0.1
        context.create_limit_order.return_value = mock_order

        result = blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "price": 45000.0,
            "amount": 0.1,
        }, context)

        self.assertEqual(result, mock_order)
        context.create_limit_order.assert_called_once()
        self.assertEqual(len(blotter.get_transactions()), 1)

        tx = blotter.get_transactions()[0]
        self.assertEqual(tx.order_id, 1)
        self.assertEqual(tx.symbol, "BTC/EUR")
        self.assertEqual(tx.price, 45000.0)
        self.assertEqual(tx.amount, 0.1)

    def test_place_market_order(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 2
        mock_order.get_symbol.return_value = "ETH/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 3000.0
        mock_order.get_amount.return_value = 1.0
        context.create_market_order.return_value = mock_order

        result = blotter.place_order({
            "target_symbol": "ETH",
            "order_side": "BUY",
            "order_type": "MARKET",
            "amount": 1.0,
        }, context)

        self.assertEqual(result, mock_order)
        context.create_market_order.assert_called_once()

    def test_slippage_applied_to_limit_order(self):
        blotter = SimulationBlotter(
            slippage_model=PercentageSlippage(0.01)
        )
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 45450.0  # slipped
        mock_order.get_amount.return_value = 0.1
        context.create_limit_order.return_value = mock_order

        blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "price": 45000.0,
            "amount": 0.1,
        }, context)

        # Verify slipped price was passed to create_limit_order
        call_kwargs = context.create_limit_order.call_args
        self.assertAlmostEqual(
            call_kwargs.kwargs["price"], 45450.0, places=0
        )

        # Check transaction records slippage
        tx = blotter.get_transactions()[0]
        self.assertGreater(tx.slippage, 0)

    def test_commission_recorded(self):
        blotter = SimulationBlotter(
            commission_model=PercentageCommission(0.001)
        )
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 45000.0
        mock_order.get_amount.return_value = 0.1
        context.create_limit_order.return_value = mock_order

        blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "price": 45000.0,
            "amount": 0.1,
        }, context)

        tx = blotter.get_transactions()[0]
        # 45000 * 0.1 * 0.001 = 4.5
        self.assertAlmostEqual(tx.commission, 4.5)
        mock_order.set_order_fee.assert_called_once_with(4.5)

    def test_cancel_order(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        mock_order = MagicMock()
        context.order_service.get.return_value = mock_order

        blotter.cancel_order(42, context)

        context.order_service.update.assert_called_once_with(
            42, {"status": "CANCELED"}
        )
        self.assertEqual(
            context.order_service.get.call_count, 2
        )

    def test_cancel_nonexistent_order_raises(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        context.order_service.get.return_value = None

        with self.assertRaises(Exception):
            blotter.cancel_order(999, context)

    def test_batch_order_with_slippage_and_commission(self):
        blotter = SimulationBlotter(
            slippage_model=FixedSlippage(amount=10.0),
            commission_model=FixedCommission(amount=5.0),
        )
        context = MagicMock()

        mock_order_1 = MagicMock()
        mock_order_1.get_id.return_value = 1
        mock_order_1.get_symbol.return_value = "BTC/EUR"
        mock_order_1.get_order_side.return_value = "BUY"
        mock_order_1.get_price.return_value = 45010.0
        mock_order_1.get_amount.return_value = 0.1

        mock_order_2 = MagicMock()
        mock_order_2.get_id.return_value = 2
        mock_order_2.get_symbol.return_value = "ETH/EUR"
        mock_order_2.get_order_side.return_value = "BUY"
        mock_order_2.get_price.return_value = 3010.0
        mock_order_2.get_amount.return_value = 1.0

        context.create_limit_order.side_effect = [
            mock_order_1, mock_order_2
        ]

        results = blotter.batch_order([
            {
                "target_symbol": "BTC",
                "order_side": "BUY",
                "price": 45000.0,
                "amount": 0.1,
            },
            {
                "target_symbol": "ETH",
                "order_side": "BUY",
                "price": 3000.0,
                "amount": 1.0,
            },
        ], context)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(blotter.get_transactions()), 2)

        # Both should have fixed commission of 5.0
        for tx in blotter.get_transactions():
            self.assertEqual(tx.commission, 5.0)

    def test_place_order_with_no_price(self):
        """Test that None price doesn't cause slippage errors."""
        blotter = SimulationBlotter(
            slippage_model=PercentageSlippage(0.01)
        )
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 0
        mock_order.get_amount.return_value = 0.1
        context.create_market_order.return_value = mock_order

        # No price, market order
        result = blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "order_type": "MARKET",
            "amount": 0.1,
        }, context)

        self.assertIsNotNone(result)
        self.assertEqual(len(blotter.get_transactions()), 1)

    def test_place_order_passes_metadata(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 45000.0
        mock_order.get_amount.return_value = 0.1
        context.create_limit_order.return_value = mock_order

        blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "price": 45000.0,
            "amount": 0.1,
            "metadata": {"strategy": "momentum"},
        }, context)

        call_kwargs = context.create_limit_order.call_args.kwargs
        self.assertEqual(
            call_kwargs["metadata"], {"strategy": "momentum"}
        )

    def test_place_order_passes_percentage_of_portfolio(self):
        blotter = SimulationBlotter()
        context = MagicMock()
        mock_order = MagicMock()
        mock_order.get_id.return_value = 1
        mock_order.get_symbol.return_value = "BTC/EUR"
        mock_order.get_order_side.return_value = "BUY"
        mock_order.get_price.return_value = 45000.0
        mock_order.get_amount.return_value = 0.5
        context.create_limit_order.return_value = mock_order

        blotter.place_order({
            "target_symbol": "BTC",
            "order_side": "BUY",
            "price": 45000.0,
            "percentage_of_portfolio": 5.0,
        }, context)

        call_kwargs = context.create_limit_order.call_args.kwargs
        self.assertEqual(call_kwargs["percentage_of_portfolio"], 5.0)


class TestSlippageModelAbstract(unittest.TestCase):

    def test_is_abstract(self):
        with self.assertRaises(TypeError):
            SlippageModel()


class TestCommissionModelAbstract(unittest.TestCase):

    def test_is_abstract(self):
        with self.assertRaises(TypeError):
            CommissionModel()


class TestImports(unittest.TestCase):
    """Test that all blotter classes are importable from the package."""

    def test_import_from_domain(self):
        from investing_algorithm_framework.domain import (  # noqa: F401
            Blotter, SimulationBlotter, Transaction,
            SlippageModel, NoSlippage, PercentageSlippage, FixedSlippage,
            CommissionModel, NoCommission, PercentageCommission,
            FixedCommission,
        )
        self.assertIsNotNone(Blotter)
        self.assertIsNotNone(SimulationBlotter)
        self.assertIsNotNone(Transaction)

    def test_import_from_top_level(self):
        from investing_algorithm_framework import (  # noqa: F401
            Blotter, SimulationBlotter, Transaction,
            NoSlippage, PercentageSlippage, FixedSlippage,
            NoCommission, PercentageCommission, FixedCommission,
        )
        self.assertIsNotNone(Blotter)
        self.assertIsNotNone(SimulationBlotter)
        self.assertIsNotNone(Transaction)


if __name__ == "__main__":
    unittest.main()
