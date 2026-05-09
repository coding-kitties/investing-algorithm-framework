"""Backtest the trend-following strategy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investing_algorithm_framework import BacktestDateRange, create_app

from strategy import TrendFollowingStrategy


def main() -> None:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    start = end - timedelta(days=365)
    date_range = BacktestDateRange(start_date=start, end_date=end)

    app = create_app()
    app.add_market(market="BITVAVO", trading_symbol="EUR",
                   initial_balance=1000)

    backtest = app.run_vector_backtest(
        strategy=TrendFollowingStrategy(),
        backtest_date_range=date_range,
        initial_amount=1000,
    )
    print(backtest)


if __name__ == "__main__":
    main()
