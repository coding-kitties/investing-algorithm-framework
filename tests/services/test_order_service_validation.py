"""Tests for the v9.0 validator refactor in ``OrderService``.

Covers:
- The two shared primitives ``_validate_sell_amount`` and
  ``_validate_buy_cash`` are composed by every order-type validator.
- STOP orders reserve buy-side cash against ``stop_price``.
- STOP_LIMIT orders reserve buy-side cash against ``price`` (limit).
- STOP_LIMIT enforces the side-specific stop-vs-limit invariant
  (BUY: limit >= stop, SELL: limit <= stop).
- Missing / non-positive reference prices are rejected at the
  primitive level.
- ``OrderStatus.is_pending`` is the canonical predicate for
  "still working at the venue".
"""

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
)
from investing_algorithm_framework.domain import OperationalException
from tests.resources import TestBase


class TestOrderServiceValidation(TestBase):
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
    # _validate_buy_cash
    # ------------------------------------------------------------------

    def test_buy_cash_within_budget_passes(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # 100 * 5 = 500 ≤ 1000 unallocated
        order_service._validate_buy_cash(
            {"amount": 100, "target_symbol": "ADA"},
            portfolio,
            reference_price=5,
        )

    def test_buy_cash_exceeds_unallocated_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        # 100 * 20 = 2000 > 1000 unallocated
        with self.assertRaises(OperationalException):
            order_service._validate_buy_cash(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=20,
            )

    def test_buy_cash_none_reference_price_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service._validate_buy_cash(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=None,
            )

    def test_buy_cash_zero_reference_price_raises(self):
        order_service = self.app.container.order_service()
        portfolio = self.app.container.portfolio_service().get(1)
        with self.assertRaises(OperationalException):
            order_service._validate_buy_cash(
                {"amount": 100, "target_symbol": "ADA"},
                portfolio,
                reference_price=0,
            )

    # ------------------------------------------------------------------
    # STOP order — reserves against stop_price
    # ------------------------------------------------------------------

    def test_stop_buy_within_budget_uses_stop_price(self):
        order_service = self.app.container.order_service()
        # 50 * 18 = 900 ≤ 1000 unallocated
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 50,
                "order_side": "BUY",
                "stop_price": 18,
                "order_type": "STOP",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual("STOP", order.get_order_type())
        # ``price`` may be 0 / None depending on the executor stub;
        # the important invariant is that the cash check used
        # ``stop_price`` to reserve and that the order survived.
        self.assertEqual(18, order.get_stop_price())

    def test_stop_buy_exceeds_budget_raises(self):
        order_service = self.app.container.order_service()
        # 100 * 20 = 2000 > 1000 unallocated
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 100,
                    "order_side": "BUY",
                    "stop_price": 20,
                    "order_type": "STOP",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    def test_stop_requires_positive_stop_price(self):
        order_service = self.app.container.order_service()
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                    "order_side": "BUY",
                    "order_type": "STOP",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    def test_stop_zero_stop_price_raises(self):
        order_service = self.app.container.order_service()
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                    "order_side": "BUY",
                    "stop_price": 0,
                    "order_type": "STOP",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    # ------------------------------------------------------------------
    # STOP_LIMIT order — reserves against limit price, enforces invariant
    # ------------------------------------------------------------------

    def test_stop_limit_buy_within_budget_uses_limit_price(self):
        order_service = self.app.container.order_service()
        # 50 * 18 = 900 ≤ 1000 unallocated; limit (18) ≥ stop (17)
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 50,
                "order_side": "BUY",
                "price": 18,
                "stop_price": 17,
                "order_type": "STOP_LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual("STOP_LIMIT", order.get_order_type())
        self.assertEqual(18, order.get_price())
        self.assertEqual(17, order.get_stop_price())

    def test_stop_limit_buy_limit_below_stop_raises(self):
        order_service = self.app.container.order_service()
        # For BUY STOP_LIMIT, limit (15) must be >= stop (17)
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                    "order_side": "BUY",
                    "price": 15,
                    "stop_price": 17,
                    "order_type": "STOP_LIMIT",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    def test_stop_limit_buy_exceeds_budget_raises(self):
        order_service = self.app.container.order_service()
        # 100 * 20 = 2000 > 1000 (cash check fires *after* invariant)
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 100,
                    "order_side": "BUY",
                    "price": 20,
                    "stop_price": 19,
                    "order_type": "STOP_LIMIT",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    def test_stop_limit_requires_positive_limit_price(self):
        order_service = self.app.container.order_service()
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 10,
                    "order_side": "BUY",
                    "stop_price": 17,
                    "order_type": "STOP_LIMIT",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )

    # ------------------------------------------------------------------
    # MARKET order — still validates with caller-supplied estimate
    # ------------------------------------------------------------------

    def test_market_buy_within_budget_uses_estimate(self):
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 5,  # estimated
                "order_type": "MARKET",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual("MARKET", order.get_order_type())

    def test_market_buy_exceeds_estimate_budget_raises(self):
        order_service = self.app.container.order_service()
        with self.assertRaises(OperationalException):
            order_service.create(
                {
                    "target_symbol": "ADA",
                    "trading_symbol": "EUR",
                    "amount": 100,
                    "order_side": "BUY",
                    "price": 50,  # 100 * 50 = 5000 > 1000
                    "order_type": "MARKET",
                    "portfolio_id": 1,
                    "status": "CREATED",
                }
            )


class TestOrderStatusIsPending(TestBase):
    """Pure unit tests for ``OrderStatus.is_pending`` — orthogonal to
    ``Order.is_triggered`` (which is timestamp-based)."""

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

    def test_open_is_pending(self):
        self.assertTrue(OrderStatus.is_pending(OrderStatus.OPEN))
        self.assertTrue(OrderStatus.is_pending("OPEN"))

    def test_created_is_not_pending(self):
        # CREATED is the default pre-execution state, not a venue
        # working state.
        self.assertFalse(OrderStatus.is_pending(OrderStatus.CREATED))
        self.assertFalse(OrderStatus.is_pending("CREATED"))

    def test_terminal_statuses_are_not_pending(self):
        for terminal in (
            OrderStatus.CLOSED,
            OrderStatus.CANCELED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        ):
            self.assertFalse(OrderStatus.is_pending(terminal))
            self.assertFalse(OrderStatus.is_pending(terminal.value))

    def test_is_pending_is_orthogonal_to_is_triggered(self):
        """A STOP order that has been triggered but not yet filled is
        still ``OPEN`` (so ``is_pending`` is True) — the trigger is
        tracked separately on the order via ``triggered_at``."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 10,
                "order_side": "BUY",
                "stop_price": 18,
                "order_type": "STOP",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        # After create(), the order has been executed by the test
        # executor and moved to OPEN.
        self.assertTrue(OrderStatus.is_pending(order.get_status()))
        self.assertFalse(order.is_triggered())

        from datetime import datetime, timezone
        order_service.update(
            order.id, {"triggered_at": datetime.now(tz=timezone.utc)}
        )
        order = order_service.get(order.id)
        self.assertTrue(OrderStatus.is_pending(order.get_status()))
        self.assertTrue(order.is_triggered())
