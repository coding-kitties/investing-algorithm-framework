"""Unit tests for the v9.0 ConflictPolicy arbitration."""
from unittest import TestCase

from investing_algorithm_framework import (
    ConflictPolicy,
    ConflictResolution,
    Signal,
    SignalSide,
)
from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)


class TestConflictPolicyDefault(TestCase):

    def setUp(self):
        self.policy = ConflictPolicy.default()

    def test_default_priority_close_before_open(self):
        # CLOSE_LONG outranks OPEN_LONG; both long-side so no
        # direction conflict.
        out = self.policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 0.9),
            Signal("BTC", SignalSide.CLOSE_LONG, 0.1),
        ], symbol="BTC")
        self.assertEqual(
            [s.side for s in out],
            [SignalSide.CLOSE_LONG, SignalSide.OPEN_LONG],
        )

    def test_default_raises_on_direction_conflict(self):
        with self.assertRaises(OperationalException) as ctx:
            self.policy.resolve([
                Signal("BTC", SignalSide.OPEN_LONG, 0.5),
                Signal("BTC", SignalSide.OPEN_SHORT, 0.5),
            ], symbol="BTC")
        self.assertIn("Direction conflict", str(ctx.exception))
        self.assertIn("BTC", str(ctx.exception))

    def test_close_long_and_close_short_not_a_conflict_under_mutex(self):
        # Two opposing closes on the same symbol IS a direction
        # conflict under strict mutex (you can't simultaneously be
        # long AND short the same name, so closing both is
        # nonsensical).
        with self.assertRaises(OperationalException):
            self.policy.resolve([
                Signal("BTC", SignalSide.CLOSE_LONG),
                Signal("BTC", SignalSide.CLOSE_SHORT),
            ], symbol="BTC")

    def test_empty_input_yields_empty_output(self):
        self.assertEqual(self.policy.resolve([], symbol="BTC"), [])

    def test_cooldown_blocks_only_open_and_scale_sides(self):
        for side in (
            SignalSide.OPEN_LONG, SignalSide.OPEN_SHORT,
            SignalSide.SCALE_IN, SignalSide.SCALE_OUT,
        ):
            self.assertTrue(
                self.policy.is_blocked_by_cooldown(side),
                f"{side} should be cooldown-blocked",
            )
        for side in (SignalSide.CLOSE_LONG, SignalSide.CLOSE_SHORT):
            self.assertFalse(
                self.policy.is_blocked_by_cooldown(side),
                f"{side} must never be cooldown-blocked",
            )


class TestConflictPolicyPriorityResolution(TestCase):

    def setUp(self):
        self.policy = ConflictPolicy.default().evolve(
            on_conflict=ConflictResolution.PRIORITY,
        )

    def test_close_side_wins_against_open_side(self):
        out = self.policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 0.9, "trend"),
            Signal("BTC", SignalSide.CLOSE_SHORT, 0.1, "risk"),
        ], symbol="BTC")
        # CLOSE_SHORT (rank 1) beats OPEN_LONG (rank 3) -> short side wins.
        self.assertEqual([s.side for s in out], [SignalSide.CLOSE_SHORT])

    def test_open_long_beats_open_short_by_priority(self):
        out = self.policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 0.1),
            Signal("BTC", SignalSide.OPEN_SHORT, 0.9),
        ], symbol="BTC")
        # priority: OPEN_LONG = 3, OPEN_SHORT = 4 -> long wins.
        self.assertEqual([s.side for s in out], [SignalSide.OPEN_LONG])


class TestConflictPolicyStrengthResolution(TestCase):

    def setUp(self):
        self.policy = ConflictPolicy.default().evolve(
            on_conflict=ConflictResolution.STRENGTH,
        )

    def test_strongest_side_wins(self):
        out = self.policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 0.3),
            Signal("BTC", SignalSide.OPEN_SHORT, 0.9),
        ], symbol="BTC")
        self.assertEqual([s.side for s in out], [SignalSide.OPEN_SHORT])

    def test_strength_tie_falls_back_to_priority(self):
        out = self.policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 0.5),
            Signal("BTC", SignalSide.OPEN_SHORT, 0.5),
        ], symbol="BTC")
        # tie -> OPEN_LONG (rank 3) wins over OPEN_SHORT (rank 4).
        self.assertEqual([s.side for s in out], [SignalSide.OPEN_LONG])


class TestConflictPolicyFactories(TestCase):

    def test_long_only_drops_short_sides(self):
        policy = ConflictPolicy.long_only()
        out = policy.resolve([
            Signal("BTC", SignalSide.OPEN_SHORT, 0.9),
            Signal("BTC", SignalSide.OPEN_LONG, 0.5),
            Signal("BTC", SignalSide.CLOSE_SHORT, 1.0),
        ], symbol="BTC")
        self.assertEqual([s.side for s in out], [SignalSide.OPEN_LONG])

    def test_short_only_drops_long_sides(self):
        policy = ConflictPolicy.short_only()
        out = policy.resolve([
            Signal("BTC", SignalSide.OPEN_LONG, 1.0),
            Signal("BTC", SignalSide.SCALE_OUT, 1.0),
            Signal("BTC", SignalSide.OPEN_SHORT, 0.5),
        ], symbol="BTC")
        self.assertEqual([s.side for s in out], [SignalSide.OPEN_SHORT])

    def test_evolve_returns_new_instance_with_changes(self):
        base = ConflictPolicy.default()
        new = base.evolve(
            on_conflict=ConflictResolution.STRENGTH,
            block_when_open_order=False,
        )
        self.assertIs(base.on_conflict, ConflictResolution.RAISE)
        self.assertIs(new.on_conflict, ConflictResolution.STRENGTH)
        self.assertTrue(base.block_when_open_order)
        self.assertFalse(new.block_when_open_order)

    def test_evolve_coerces_priority_and_cooldown_blocks(self):
        new = ConflictPolicy.default().evolve(
            priority=[SignalSide.OPEN_LONG, SignalSide.CLOSE_LONG],
            cooldown_blocks={SignalSide.OPEN_LONG},
        )
        self.assertEqual(
            new.priority,
            (SignalSide.OPEN_LONG, SignalSide.CLOSE_LONG),
        )
        self.assertEqual(
            new.cooldown_blocks, frozenset({SignalSide.OPEN_LONG}),
        )
