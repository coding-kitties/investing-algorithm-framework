import unittest
from datetime import datetime, timezone

from investing_algorithm_framework.domain.fx import (
    FXRateProvider, StaticFXRateProvider,
)


class TestFXRateProviderABC(unittest.TestCase):
    """Verify that FXRateProvider is an abstract base class."""

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            FXRateProvider()

    def test_subclass_must_implement_get_rate(self):

        class Incomplete(FXRateProvider):
            pass

        with self.assertRaises(TypeError):
            Incomplete()

    def test_subclass_with_get_rate_works(self):

        class Concrete(FXRateProvider):
            def get_rate(self, from_currency, to_currency, date=None):
                return 1.0

        provider = Concrete()
        self.assertEqual(provider.get_rate("USD", "USD"), 1.0)

    def test_supports_pair_default_returns_true(self):

        class Concrete(FXRateProvider):
            def get_rate(self, from_currency, to_currency, date=None):
                return 1.0

        provider = Concrete()
        self.assertTrue(provider.supports_pair("USD", "EUR"))


class TestStaticFXRateProvider(unittest.TestCase):

    def test_direct_rate(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        self.assertAlmostEqual(provider.get_rate("USD", "EUR"), 0.92)

    def test_inverse_rate(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        expected = 1.0 / 0.92
        self.assertAlmostEqual(provider.get_rate("EUR", "USD"), expected)

    def test_same_currency_returns_one(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        self.assertEqual(provider.get_rate("USD", "USD"), 1.0)

    def test_case_insensitive(self):
        provider = StaticFXRateProvider({("usd", "eur"): 0.92})
        self.assertAlmostEqual(provider.get_rate("USD", "EUR"), 0.92)
        self.assertAlmostEqual(
            provider.get_rate("eur", "usd"), 1.0 / 0.92
        )

    def test_missing_pair_raises(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})

        with self.assertRaises(ValueError) as ctx:
            provider.get_rate("GBP", "JPY")

        self.assertIn("GBP/JPY", str(ctx.exception))

    def test_add_rate(self):
        provider = StaticFXRateProvider()
        provider.add_rate("GBP", "EUR", 1.17)
        self.assertAlmostEqual(provider.get_rate("GBP", "EUR"), 1.17)

    def test_add_rate_updates_existing(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        provider.add_rate("USD", "EUR", 0.95)
        self.assertAlmostEqual(provider.get_rate("USD", "EUR"), 0.95)

    def test_supports_pair_true(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        self.assertTrue(provider.supports_pair("USD", "EUR"))
        # Inverse also supported
        self.assertTrue(provider.supports_pair("EUR", "USD"))

    def test_supports_pair_false(self):
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        self.assertFalse(provider.supports_pair("GBP", "JPY"))

    def test_supports_pair_same_currency(self):
        provider = StaticFXRateProvider()
        self.assertTrue(provider.supports_pair("USD", "USD"))

    def test_multiple_pairs(self):
        provider = StaticFXRateProvider({
            ("USD", "EUR"): 0.92,
            ("GBP", "EUR"): 1.17,
            ("USD", "GBP"): 0.79,
        })
        self.assertAlmostEqual(provider.get_rate("USD", "EUR"), 0.92)
        self.assertAlmostEqual(provider.get_rate("GBP", "EUR"), 1.17)
        self.assertAlmostEqual(provider.get_rate("USD", "GBP"), 0.79)
        # All inverses
        self.assertAlmostEqual(
            provider.get_rate("EUR", "USD"), 1.0 / 0.92
        )
        self.assertAlmostEqual(
            provider.get_rate("EUR", "GBP"), 1.0 / 1.17
        )
        self.assertAlmostEqual(
            provider.get_rate("GBP", "USD"), 1.0 / 0.79
        )

    def test_date_parameter_ignored(self):
        """Static provider ignores date — always returns the same rate."""
        provider = StaticFXRateProvider({("USD", "EUR"): 0.92})
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.assertAlmostEqual(
            provider.get_rate("USD", "EUR", date=dt), 0.92
        )

    def test_empty_init(self):
        provider = StaticFXRateProvider()
        self.assertTrue(provider.supports_pair("USD", "USD"))

        with self.assertRaises(ValueError):
            provider.get_rate("USD", "EUR")


if __name__ == "__main__":
    unittest.main()
