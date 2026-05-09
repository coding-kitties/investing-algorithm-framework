"""Integration tests for ``Context.sync_portfolio`` and the auto-sync hook."""
from datetime import datetime, timezone

from investing_algorithm_framework import (
    MarketCredential,
    PortfolioConfiguration,
    PortfolioOutOfSyncError,
    ScheduledDeposit,
    SyncResult,
    TimeUnit,
)
from investing_algorithm_framework.domain import (
    ENVIRONMENT,
    Environment,
    INDEX_DATETIME,
)
from tests.resources import TestBase


def _utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


class TestSyncPortfolioLiveMode(TestBase):
    """Live (TEST env hits the live code path) — broker is the stub
    ``PortfolioProviderTest`` whose balance we mutate directly."""

    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(market="binance", api_key="x", secret_key="y")
    ]
    external_balances = {"EUR": 1000}

    def setUp(self) -> None:
        super().setUp()
        # The TestBase registers the stub provider; ensure it answers for
        # 'binance' explicitly.
        lookup = self.app.container.portfolio_provider_lookup()
        lookup.register_portfolio_provider_for_market("binance")
        provider = lookup.get_portfolio_provider("binance")
        provider.external_balances = {"EUR": 1000}
        self._provider = provider

    def _broker(self):
        return self._provider

    def test_noop_when_in_sync(self):
        result = self.app.context.sync_portfolio(market="binance")
        self.assertIsInstance(result, SyncResult)
        self.assertEqual("noop", result.kind)
        self.assertEqual(0.0, result.delta)
        self.assertEqual(1000.0, result.new_unallocated)

    def test_deposit_absorbed(self):
        self._broker().external_balances = {"EUR": 1300}
        result = self.app.context.sync_portfolio(market="binance")
        self.assertEqual("deposit", result.kind)
        self.assertEqual(300.0, result.delta)
        self.assertEqual(1300.0, result.new_unallocated)
        # Persisted to the portfolio
        portfolio = self.app.container.portfolio_service() \
            .find({"market": "binance"})
        self.assertEqual(1300.0, portfolio.get_unallocated())

    def test_withdrawal_raises_by_default(self):
        self._broker().external_balances = {"EUR": 800}
        with self.assertRaises(PortfolioOutOfSyncError) as ctx:
            self.app.context.sync_portfolio(market="binance")
        err = ctx.exception
        self.assertEqual("BINANCE", err.market)
        self.assertEqual(1000.0, err.local_unallocated)
        self.assertEqual(800.0, err.broker_available)
        self.assertEqual(-200.0, err.delta)
        # State must NOT have changed
        portfolio = self.app.container.portfolio_service() \
            .find({"market": "binance"})
        self.assertEqual(1000.0, portfolio.get_unallocated())

    def test_withdrawal_allowed_when_opted_in(self):
        self._broker().external_balances = {"EUR": 800}
        result = self.app.context.sync_portfolio(
            market="binance", allow_withdrawals=True
        )
        self.assertEqual("withdrawal", result.kind)
        self.assertEqual(-200.0, result.delta)
        self.assertEqual(800.0, result.new_unallocated)

    def test_negative_broker_balance_always_raises(self):
        self._broker().external_balances = {"EUR": -5}
        with self.assertRaises(PortfolioOutOfSyncError):
            self.app.context.sync_portfolio(
                market="binance", allow_withdrawals=True
            )


class TestSyncPortfolioBacktestMode(TestBase):
    """Backtest mode — sync_portfolio reads pending deposits from the
    BrokerBalanceTracker rather than from a live broker."""

    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(market="binance", api_key="x", secret_key="y")
    ]
    external_balances = {"EUR": 1000}

    def setUp(self) -> None:
        super().setUp()
        # Flip the env to BACKTEST so sync_portfolio uses the tracker.
        self.app.container.configuration_service().add_value(
            ENVIRONMENT, Environment.BACKTEST.value
        )

    def _tracker(self):
        return self.app.container.broker_balance_tracker()

    def test_noop_when_no_pending(self):
        result = self.app.context.sync_portfolio(market="binance")
        self.assertEqual("noop", result.kind)

    def test_pending_deposit_absorbed(self):
        tracker = self._tracker()
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=250.0, on=_utc(2024, 1, 5))],
        )
        # Anchor + fire after the one-shot
        tracker.fire_due_deposits("binance", _utc(2024, 1, 1))
        tracker.fire_due_deposits("binance", _utc(2024, 1, 6))

        result = self.app.context.sync_portfolio(market="binance")
        self.assertEqual("deposit", result.kind)
        self.assertEqual(250.0, result.delta)
        self.assertEqual(1250.0, result.new_unallocated)

        # Pending was drained.
        self.assertEqual(0.0, tracker.peek_pending("binance"))

        # Calling again is a noop.
        result2 = self.app.context.sync_portfolio(market="binance")
        self.assertEqual("noop", result2.kind)

    def test_negative_pending_raises_without_opt_in(self):
        tracker = self._tracker()
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=-200.0, on=_utc(2024, 1, 5))],
        )
        tracker.fire_due_deposits("binance", _utc(2024, 1, 1))
        tracker.fire_due_deposits("binance", _utc(2024, 1, 6))

        with self.assertRaises(PortfolioOutOfSyncError):
            self.app.context.sync_portfolio(market="binance")

    def test_negative_pending_allowed(self):
        tracker = self._tracker()
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=-200.0, on=_utc(2024, 1, 5))],
        )
        tracker.fire_due_deposits("binance", _utc(2024, 1, 1))
        tracker.fire_due_deposits("binance", _utc(2024, 1, 6))

        result = self.app.context.sync_portfolio(
            market="binance", allow_withdrawals=True
        )
        self.assertEqual("withdrawal", result.kind)
        self.assertEqual(-200.0, result.delta)
        self.assertEqual(800.0, result.new_unallocated)
