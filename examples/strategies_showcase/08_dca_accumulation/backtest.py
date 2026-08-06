"""Backtest the DCA strategy with a recurring monthly deposit."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestWindow,
    ScheduledDeposit,
    Study,
    TimeUnit,
    Universe,
    create_app,
)

from strategy import DCAStrategy


def main() -> None:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    start = end - timedelta(days=730)

    study = Study(
        name="dca-accumulation",
        universe=Universe(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_capital=2500,
        ),
        backtest_windows=[
            BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=start,
                    end_date=end,
                )
            )
        ],
    )

    app = create_app()
    app.add_strategy(DCAStrategy)
    # Deposit schedule is set at the market level (not yet in Universe)
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
    backtests = app.run_backtest(strategy=DCAStrategy, study=study)
    backtest = backtests[0]
    metrics = backtest.get_backtest_metrics(study_name=study.name)
    print(metrics)


if __name__ == "__main__":
    main()
