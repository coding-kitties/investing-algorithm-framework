"""Backtest the machine-learning strategy.

Assumes ``model.pkl`` (a pickled classifier exposing ``predict_proba``)
sits next to this file.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestWindow,
    Study,
    Universe,
    create_app,
)

from strategy import MachineLearningStrategy


MODEL_PATH = Path(__file__).parent / "model.pkl"


def main() -> None:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    start = end - timedelta(days=365)

    strategy = MachineLearningStrategy(
        model_path=MODEL_PATH,
        symbol="BTC/EUR",
        time_frame="1d",
        enter_threshold=0.55,
        exit_threshold=0.45,
    )

    study = Study(
        name="ml-strategy",
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
    app.add_strategy(strategy)
    backtests = app.run_backtest(strategy=strategy, study=study)
    backtest = backtests[0]
    metrics = backtest.get_backtest_metrics(study_name=study.name)
    print(metrics)


if __name__ == "__main__":
    main()
