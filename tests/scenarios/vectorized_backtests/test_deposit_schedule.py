"""Unit test for VectorBacktestService._resolve_deposit_schedule."""
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    PortfolioConfiguration,
    ScheduledDeposit,
    TimeUnit,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import VectorBacktestService


def _utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


class TestVectorBacktestDepositSchedule(TestCase):

    def test_no_schedule_returns_empty(self):
        config = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        events = VectorBacktestService._resolve_deposit_schedule(
            portfolio_configuration=config,
            backtest_date_range=BacktestDateRange(
                start_date=_utc(2024, 1, 1),
                end_date=_utc(2024, 6, 1),
            ),
        )
        self.assertEqual([], events)

    def test_recurring_and_one_shot_combined(self):
        config = PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_balance=1000,
            deposit_schedule=[
                ScheduledDeposit(
                    amount=100.0, time_unit=TimeUnit.DAY, interval=30
                ),
                ScheduledDeposit(amount=500.0, on=_utc(2024, 2, 15)),
            ],
        )
        events = VectorBacktestService._resolve_deposit_schedule(
            portfolio_configuration=config,
            backtest_date_range=BacktestDateRange(
                start_date=_utc(2024, 1, 1),
                end_date=_utc(2024, 4, 1),
            ),
        )
        self.assertEqual(
            [
                (_utc(2024, 1, 31), 100.0),
                (_utc(2024, 2, 15), 500.0),
                (_utc(2024, 3, 1), 100.0),
                (_utc(2024, 3, 31), 100.0),
            ],
            events,
        )
