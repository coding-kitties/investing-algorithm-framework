from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework import Signal, SignalSide
from investing_algorithm_framework.services.order_service.order_service import OrderService
from investing_algorithm_framework.services.strategy_phases.apply_risk_budget import ApplyRiskBudgetPhase
from investing_algorithm_framework.services.strategy_phases.phase_state import PhaseState, SizedIntent


class TestSharedLiveAndEventCashChecks(TestCase):
    def setUp(self):
        self.service = object.__new__(OrderService)
        self.service.position_service = Mock()
        third = 1000 * ((100 / 3) / 100)
        self.available = 1000 - 2 * third
        position = self.service.position_service.find.return_value
        position.get_amount.return_value = self.available
        self.portfolio = SimpleNamespace(id=1, trading_symbol="USD", unallocated=self.available)

    def test_shared_buy_and_short_guards_allow_thirds_roundoff(self):
        third = 1000 * ((100 / 3) / 100)
        price = 93.09566466522216
        order = {"amount": third / price, "target_symbol": "QQQ"}
        self.assertGreater(order["amount"] * price, self.available)
        for validator in (
            self.service._validate_buy_cash,
            self.service._validate_short_collateral,
        ):
            validator(order, self.portfolio, reference_price=price)

    def test_shared_guards_still_reject_genuine_overspend(self):
        price = 100
        order = {"amount": (self.available + 0.01) / price, "target_symbol": "QQQ"}
        for validator in (
            self.service._validate_buy_cash,
            self.service._validate_short_collateral,
        ):
            with self.assertRaises(OperationalException):
                validator(order, self.portfolio, reference_price=price)

    def test_scale_in_survives_risk_budget_and_shared_order_validation(self):
        third = 1000 * ((100 / 3) / 100)
        price = 93.09566466522216
        context = Mock()
        context.get_unallocated.return_value = self.available
        state = PhaseState(
            strategy=SimpleNamespace(exposure_rule=None),
            context=context,
            data={},
            current_datetime=datetime(2025, 1, 1, tzinfo=timezone.utc),
            sized_intents=[
                SizedIntent(
                    signal=Signal("QQQ", SignalSide.SCALE_IN),
                    amount=third / price,
                    price=price,
                    quote_amount=third,
                    full_symbol="QQQ/USD",
                    order_reason="scale_in",
                ),
            ],
        )
        with self.assertLogs(
            "investing_algorithm_framework.services.strategy_phases.apply_risk_budget",
            level="WARNING",
        ):
            ApplyRiskBudgetPhase().run(state)
        self.assertEqual(len(state.sized_intents), 1)
        intent = state.sized_intents[0]
        self.assertAlmostEqual(intent.quote_amount, self.available, places=12)
        self.service._validate_buy_cash(
            {"amount": intent.amount, "target_symbol": "QQQ"},
            self.portfolio,
            reference_price=intent.price,
        )
