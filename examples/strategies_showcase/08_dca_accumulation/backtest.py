"""Backtest the DCA strategy with a recurring monthly deposit."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    ScheduledDeposit,
    TimeUnit,
    create_app,
)

from strategy import DCAStrategy


def main() -> None:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    start = end - timedelta(days=730)
    date_range = BacktestDateRange(start_date=start, end_date=end)

    app = create_app()
    app.add_strategy(DCAStrategy)
    app.add_market(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=2500,
        deposit_schedule=[
            ScheduledDeposit(
                amount=100.0, time_unit=TimeUnit.DAY, interval=30
            ),
        ],
        auto_sync=True,
    )

    backtest = app.run_backtest(backtest_date_range=date_range)
    print(backtest)


if __name__ == "__main__":
    main()
