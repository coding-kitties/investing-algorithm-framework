from unittest import TestCase

from investing_algorithm_framework import Position


class TestPosition(TestCase):

	def test_legacy_long_values_populate_long_leg(self):
		position = Position(symbol="BTC", amount=2, cost=200)

		self.assertEqual(2, position.long_amount)
		self.assertEqual(0, position.short_amount)
		self.assertEqual(200, position.long_cost)
		self.assertEqual(0, position.short_cost)
		self.assertEqual(2, position.amount)
		self.assertEqual(200, position.cost)

	def test_legacy_short_values_populate_positive_short_leg(self):
		position = Position(symbol="BTC", amount=-2, cost=200)

		self.assertEqual(0, position.long_amount)
		self.assertEqual(2, position.short_amount)
		self.assertEqual(0, position.long_cost)
		self.assertEqual(200, position.short_cost)
		self.assertEqual(-2, position.amount)
		self.assertEqual(200, position.cost)

	def test_explicit_legs_expose_net_and_gross_values(self):
		position = Position(
			symbol="BTC",
			long_amount=5,
			short_amount=3,
			long_cost=500,
			short_cost=330,
		)

		self.assertEqual(2, position.amount)
		self.assertEqual(8, position.gross_amount)
		self.assertEqual(500, position.cost)
		self.assertEqual(170, position.net_cost)
		self.assertEqual(830, position.gross_cost)

	def test_legacy_amount_mutation_has_netting_semantics(self):
		position = Position(
			symbol="BTC",
			long_amount=5,
			short_amount=3,
			long_cost=500,
			short_cost=330,
		)

		position.amount = -4

		self.assertEqual(0, position.long_amount)
		self.assertEqual(4, position.short_amount)
		self.assertEqual(0, position.long_cost)
		self.assertEqual(500, position.short_cost)

	def test_serialization_upgrades_old_payload_and_preserves_legs(self):
		old_position = Position.from_dict({
			"symbol": "BTC", "amount": -2, "cost": 200
		})
		restored = Position.from_dict(old_position.to_dict())

		self.assertEqual(-2, restored.amount)
		self.assertEqual(2, restored.short_amount)
		self.assertEqual(200, restored.short_cost)

	def test_leg_values_must_be_nonnegative(self):
		with self.assertRaises(ValueError):
			Position(symbol="BTC", short_amount=-1)
