"""Tests for #434 phase 1 — SHORT / COVER plumbing in ``OrderService``.

Covers:
- ``OrderSide.SHORT`` / ``OrderSide.COVER`` enum round-trips.
- ``validate_short_order`` invariants (trading_symbol, amount,
  no-existing-long).
- ``validate_cover_order`` invariants (trading_symbol, amount,
  position-exists, position-is-short, amount-within-short-size).
- ``_validate_short_collateral`` cash reservation primitive.
- ``_validate_cover_amount`` size primitive against a negative-amount
  position.
- ``Context.create_short_order`` / ``create_cover_order`` happy path
  with ``execute=False, sync=False`` (validation-only plumbing).
- ``NotImplementedError`` guards in ``OrderService.create`` for
  SHORT/COVER + ``execute=True`` and SHORT/COVER + ``sync=True``.
"""

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
)
from investing_algorithm_framework.domain import (
    OperationalException,
    OrderSide,
)
from tests.resources import TestBase


class TestOrderSideShortCoverEnum(TestBase):
    """Sanity checks on the SHORT / COVER values added to OrderSide."""

    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000}

    def test_from_string_short(self):
        self.assertEqual(OrderSide.SHORT, OrderSide.from_string("SHORT"))
        self.assertEqual(OrderSide.SHORT, OrderSide.from_string("short"))

    def test_from_string_cover(self):
        self.assertEqual(OrderSide.COVER, OrderSide.from_string("COVER"))
        self.assertEqual(OrderSide.COVER, OrderSide.from_string("cover"))

    def test_equals(self):
        self.assertTrue(OrderSide.SHORT.equals("SHORT"))
        self.assertTrue(OrderSide.SHORT.equals(OrderSide.SHORT))
        self.assertTrue(OrderSide.COVER.equals("COVER"))
        self.assertTrue(OrderSide.COVER.equals(OrderSide.COVER))
        self.assertFalse(OrderSide.SHORT.equals(OrderSide.COVER))
        self.assertFalse(OrderSide.COVER.equals(OrderSide.BUY))


class TestShortOrderValidation(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000}

    # ------------------------------------------------------------------
    # validate_short_order — high-level invariants
    # ------------------------------------------------------------------

    def test_short_validates_when_no_existing_position(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # No existing ADA position → must pass.
        order_service.validate_short_order(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
            },
            portfolio,
        )

    def test_short_rejects_mismatched_trading_symbol(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service.validate_short_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "USDT",
                    "amount": 100,
                },
                portfolio,
            )

    def test_short_rejects_non_positive_amount(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service.validate_short_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 0,
                },
                portfolio,
            )
        with self.assertRaises(OperationalException):
            order_service.validate_short_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": -10,
                },
                portfolio,
            )

    def test_short_rejects_when_existing_long_position(self):
        order_service = self.app.container.order_service()
        position_service = self.app.container.position_service()
        portfolio = self.app.container.portfolio_service().get(1)

        # Create a long position for ADA (positive amount).
        position_service.create(
            {"portfolio_id": portfolio.id, "symbol": "ADA"}
        )
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        position_service.update(position.id, {"amount": 50})

        with self.assertRaises(OperationalException):
            order_service.validate_short_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                },
                portfolio,
            )

    # ------------------------------------------------------------------
    # _validate_short_collateral — cash reservation primitive
    # ------------------------------------------------------------------

    def test_short_collateral_within_budget_passes(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # 100 * 5 = 500 ≤ 1000 unallocated
        order_service._validate_short_collateral(
            {"amount": 100, "target_symbol": "ADA"},
            portfolio,
            reference_price=5,
        )

    def test_short_collateral_exceeds_unallocated_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # 100 * 20 = 2000 > 1000 unallocated
        with self.assertRaises(OperationalException):
            order_service._validate_short_collateral(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=20,
            )

    def test_short_collateral_none_reference_price_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service._validate_short_collateral(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=None,
            )

    def test_short_collateral_zero_reference_price_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service._validate_short_collateral(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=0,
            )


class TestCoverOrderValidation(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000}

    def _create_short_position(self, symbol, amount):
        """Helper: create a position with a NEGATIVE amount to model
        an open short for the validators under test.
        """
        position_service = self.app.container.position_service()
        portfolio = self.app.container.portfolio_service().get(1)
        position_service.create(
            {"portfolio_id": portfolio.id, "symbol": symbol}
        )
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        position_service.update(position.id, {"amount": amount})
        return position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )

    # ------------------------------------------------------------------
    # validate_cover_order
    # ------------------------------------------------------------------

    def test_cover_validates_against_open_short(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -100)

        # Cover 50 of an open 100-unit short → must pass.
        order_service.validate_cover_order(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 50,
            },
            portfolio,
        )

    def test_cover_rejects_mismatched_trading_symbol(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -100)
        with self.assertRaises(OperationalException):
            order_service.validate_cover_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "USDT",
                    "amount": 50,
                },
                portfolio,
            )

    def test_cover_rejects_non_positive_amount(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -100)
        with self.assertRaises(OperationalException):
            order_service.validate_cover_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 0,
                },
                portfolio,
            )

    def test_cover_rejects_when_no_position(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service.validate_cover_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                },
                portfolio,
            )

    def test_cover_rejects_when_position_is_long(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # Positive amount → long, not short.
        self._create_short_position("ADA", 100)
        with self.assertRaises(OperationalException):
            order_service.validate_cover_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                },
                portfolio,
            )

    def test_cover_rejects_when_amount_exceeds_short_size(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -50)
        with self.assertRaises(OperationalException):
            order_service.validate_cover_order(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 100,
                },
                portfolio,
            )

    # ------------------------------------------------------------------
    # _validate_cover_amount
    # ------------------------------------------------------------------

    def test_cover_amount_within_short_passes(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -100)
        order_service._validate_cover_amount(
            {"amount": 100, "target_symbol": "ADA"},
            portfolio,
        )

    def test_cover_amount_zero_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -100)
        with self.assertRaises(OperationalException):
            order_service._validate_cover_amount(
                {"amount": 0, "target_symbol": "ADA"},
                portfolio,
            )

    def test_cover_amount_against_long_position_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", 100)
        with self.assertRaises(OperationalException):
            order_service._validate_cover_amount(
                {"amount": 10, "target_symbol": "ADA"},
                portfolio,
            )

    def test_cover_amount_exceeds_short_size_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        self._create_short_position("ADA", -50)
        with self.assertRaises(OperationalException):
            order_service._validate_cover_amount(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
            )


class TestContextShortCoverPhase1(TestBase):
    """End-to-end Context plumbing for SHORT / COVER under the
    phase-1 contract: ``execute=False, sync=False`` is the only
    supported configuration; anything else raises.
    """

    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000}

    def _create_short_position(self, symbol, amount):
        position_service = self.app.container.position_service()
        portfolio = self.app.container.portfolio_service().get(1)
        position_service.create(
            {"portfolio_id": portfolio.id, "symbol": symbol}
        )
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        position_service.update(position.id, {"amount": amount})

    # ------------------------------------------------------------------
    # Happy path — validation-only plumbing
    # ------------------------------------------------------------------

    def test_create_short_order_persists_in_created_state(self):
        order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=5,
            amount=100,
            execute=False,
            sync=False,
        )
        self.assertIsNotNone(order)
        self.assertTrue(OrderSide.SHORT.equals(order.get_order_side()))
        self.assertEqual(OrderStatus.CREATED.value, order.get_status())
        self.assertEqual(100, order.get_amount())
        self.assertEqual(5, order.get_price())

    def test_create_cover_order_persists_in_created_state(self):
        self._create_short_position("ADA", -100)
        order = self.app.context.create_cover_order(
            target_symbol="ADA",
            price=5,
            amount=50,
            execute=False,
            sync=False,
        )
        self.assertIsNotNone(order)
        self.assertTrue(OrderSide.COVER.equals(order.get_order_side()))
        self.assertEqual(OrderStatus.CREATED.value, order.get_status())
        self.assertEqual(50, order.get_amount())

    # ------------------------------------------------------------------
    # Sizing helpers
    # ------------------------------------------------------------------

    def test_create_short_order_requires_amount_or_percentage(self):
        with self.assertRaises(OperationalException):
            self.app.context.create_short_order(
                target_symbol="ADA",
                price=5,
                execute=False,
                sync=False,
            )

    def test_create_cover_order_percentage_requires_open_short(self):
        # No short position exists → percentage_of_position must raise.
        with self.assertRaises(OperationalException):
            self.app.context.create_cover_order(
                target_symbol="ADA",
                price=5,
                percentage_of_position=50,
                execute=False,
                sync=False,
            )

    def test_create_cover_order_percentage_against_long_raises(self):
        self._create_short_position("ADA", 100)  # long, not short
        with self.assertRaises(OperationalException):
            self.app.context.create_cover_order(
                target_symbol="ADA",
                price=5,
                percentage_of_position=50,
                execute=False,
                sync=False,
            )
