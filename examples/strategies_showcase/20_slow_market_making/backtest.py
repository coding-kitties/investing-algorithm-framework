"""Backtest the Slow market-making strategy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestWindow,
    Study,
    Universe,
    create_app,
)

from strategy import SlowMarketMakingStrategy


def main() -> None:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    start = end - timedelta(days=60)

    study = Study(
        name="slow-market-making",
        universe=Universe(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_capital=1000,
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
    app.add_strategy(SlowMarketMakingStrategy)
    backtests = app.run_backtest(strategy=SlowMarketMakingStrategy, study=study)
    backtest = backtests[0]
    metrics = backtest.get_backtest_metrics(study_name=study.name)
    print(metrics)


if __name__ == "__main__":
    main()
