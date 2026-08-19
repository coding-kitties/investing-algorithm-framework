"""Backtest the advanced multi-signal strategy.

Self-contained: generates deterministic synthetic OHLCV data on first
run (no network, no API keys) and runs the strategy through the
event-driven backtest engine.
"""
from __future__ import annotations

from pathlib import Path

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    CSVOHLCVDataProvider,
    RESOURCE_DIRECTORY,
    Study,
    Universe,
    create_app,
)

from generate_data import BACKTEST_START_DATE, END_DATE, generate_if_missing
from strategy import AdvancedMultiSignalStrategy
from tasks import PortfolioHeartbeatTask


def main() -> None:
    csv_path = generate_if_missing()

    app = create_app(
        config={RESOURCE_DIRECTORY: str(Path(__file__).parent)}
    )
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10_000
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=str(csv_path),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=60,
        ),
        priority=1,
    )

    strategy = AdvancedMultiSignalStrategy()
    app.add_strategy(strategy)
    app.add_task(PortfolioHeartbeatTask())

    date_range = BacktestDateRange(
        start_date=BACKTEST_START_DATE, end_date=END_DATE
    )
    study = Study(
        universe=Universe(market="BITVAVO", trading_symbol="EUR"),
        risk_free_rate=0.03,
        backtest_windows=[BacktestWindow(train_range=date_range)],
        engines=[BacktestEngine.EVENT_DRIVEN],
    )
    backtests = app.run_backtest(strategy=strategy, study=study)
    backtest = backtests[0]
    run = backtest.get_all_backtest_runs()[0]

    print(f"\nTrades: {len(run.get_trades())}")
    print(f"Orders: {len(run.orders)}")
    print("\nStrategy trade log (first 20 entries):")
    for line in strategy.trade_log[:20]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
