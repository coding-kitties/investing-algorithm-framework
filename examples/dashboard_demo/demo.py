"""Run offline confluence backtests and render dedicated dashboard examples."""

import argparse
import logging
import os
import subprocess
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd
from pyindicators import rsi

from investing_algorithm_framework import (
    RESOURCE_DIRECTORY,
    BacktestDateRange,
    BacktestEngine,
    BacktestReport,
    BacktestRunConfiguration,
    BacktestWindow,
    ConfluenceScoreConfig,
    ConfluenceScoringStrategy,
    CooldownRule,
    CSVOHLCVDataProvider,
    DataSource,
    IndicatorConfig,
    IndicatorRule,
    PositionSize,
    Schedule,
    SignalSide,
    StopLossRule,
    Study,
    TakeProfitRule,
    TimeUnit,
    Universe,
    create_app,
)


class DashboardStrategy(ConfluenceScoringStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            identifier="BTC_ohlcv",
            symbol="BTC/EUR",
            data_type="OHLCV",
            time_frame="2h",
            market="BITVAVO",
            pandas=True,
            warmup_window=100,
        )
    ]
    indicator_configs = [
        IndicatorConfig(
            id="rsi",
            calculate=rsi,
            timeframe="2h",
            data_source="BTC_ohlcv",
            parameters={
                "source_column": "Close",
                "period": 14,
                "result_column": "rsi",
            },
            output_columns=["rsi"],
            minimum_history=15,
            history="continuous",
            execution="precompute",
        )
    ]
    confluence_cards = [
        ConfluenceScoreConfig(
            id=name,
            side=side,
            symbols=["BTC"],
            rules={
                "rsi_threshold": IndicatorRule(
                    indicator_id="rsi",
                    output_column="rsi",
                    threshold=threshold,
                    comparison=comparison,
                    group_weights={"primary": 1},
                    lookback_period=1,
                )
            },
            group_aggregation={"primary": "sum"},
            group_thresholds={"primary": 1},
        )
        for name, side, threshold, comparison in (
            ("long_entry", SignalSide.OPEN_LONG, 30, "le"),
            ("long_exit", SignalSide.CLOSE_LONG, 70, "ge"),
            ("short_entry", SignalSide.OPEN_SHORT, 70, "ge"),
            ("short_exit", SignalSide.CLOSE_SHORT, 30, "le"),
        )
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20)
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100,
        )
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=10, sell_percentage=100,
        )
    ]
    cooldowns = [CooldownRule(trigger="any", blocks="any", bars=2)]


def create_prices():
    index = pd.date_range(
        "2024-01-01", periods=1200, freq="2h", tz="UTC",
    )
    bars = np.arange(len(index))
    close = 100 + 12 * np.sin(bars * np.pi / 30) + bars * 0.005
    previous = np.concatenate(([close[0]], close[:-1]))
    return pd.DataFrame({
        "Open": previous,
        "High": np.maximum(previous, close) + 1,
        "Low": np.minimum(previous, close) - 1,
        "Close": close,
        "Volume": 1000.0,
    }, index=index)


def run_backtests(output):
    for label in ("vector", "event"):
        directory = output / label / "backtests"
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(
                f"{directory} already contains results. Use --reports-only "
                "to rebuild dashboards, or --output with a fresh directory "
                "to run new backtests."
            )
    output.mkdir(parents=True, exist_ok=True)
    prices = create_prices()
    csv_path = output / "prices.csv"
    prices.rename_axis("Datetime").reset_index().to_csv(csv_path, index=False)
    windows = [
        BacktestWindow(train_range=BacktestDateRange(
            name="early-2024",
            start_date=prices.index[100].to_pydatetime(),
            end_date=prices.index[-1].to_pydatetime(),
        ))
    ]

    for label, engine in (
        ("vector", BacktestEngine.VECTOR),
        ("event", BacktestEngine.EVENT_DRIVEN),
    ):
        app = create_app(
            name=f"dashboard-demo-{label}",
            config={RESOURCE_DIRECTORY: str(output / label / "resources")},
        )
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=10_000,
        )
        app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv_path),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=100,
        ), priority=1)
        study = Study(
            name="dashboard-demo",
            initial_capital=10_000,
            universe=Universe(
                market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
            ),
            engines=[engine],
            backtest_windows=windows,
        )
        results = app.run_backtest(
            strategy=DashboardStrategy(algorithm_id="dashboard-demo"),
            study=study,
            run_configuration=BacktestRunConfiguration(
                n_workers=0,
                show_progress=False,
                continue_on_error=False,
                use_checkpoints=False,
                capture_run_reports=label == "event",
                persist_run_reports=label == "event",
                backtest_storage_directory=str(output / label / "backtests"),
            ),
        )
        for backtest in results.iter_backtests():
            for run in backtest.get_runs(label):
                print(
                    f"{label}: {run.backtest_window.train_range.name}: "
                    f"{len(run.trades)} trades, {len(run.orders)} orders",
                    flush=True,
                )
                if not run.trades:
                    raise RuntimeError(
                        f"The {label} demo produced no trades; "
                        "the dashboard would have no trading activity."
                    )


def build_reports(output):
    directories = [
        str(output / label / "backtests") for label in ("vector", "event")
    ]
    for label, directory in zip(("vector", "event"), directories):
        path = output / f"{label}.html"
        BacktestReport.open(directory_path=directory).save(str(path))
        print(f"{label} dashboard: {path}", flush=True)

    path = output / "comparison.html"
    BacktestReport.open(directory_path=directories).save(str(path))
    print(f"Comparison dashboard: {path}", flush=True)
    return path


def open_dashboard(path):
    if os.environ.get("WSL_DISTRO_NAME"):
        windows_path = subprocess.run(
            ["wslpath", "-w", str(path.resolve())],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        quoted_path = windows_path.replace("'", "''")
        subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "$ErrorActionPreference = 'Stop'; "
                f"Start-Process -FilePath '{quoted_path}'",
            ],
            check=True,
        )
        return True
    return webbrowser.open(path.as_uri(), new=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="Directory for CSV data, saved backtests and HTML dashboards.",
    )
    parser.add_argument(
        "--reports-only", action="store_true",
        help="Regenerate dashboards from saved bundles without backtesting.",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Save dashboards without opening a browser (for headless runs).",
    )
    args = parser.parse_args()
    logging.getLogger("investing_algorithm_framework").setLevel(
        logging.WARNING
    )
    output = args.output.resolve()
    if not args.reports_only:
        run_backtests(output)
    report_path = build_reports(output)
    if not args.no_browser and not open_dashboard(report_path):
        logging.getLogger(__name__).warning(
            "Could not open a browser. Open the dashboard manually: %s",
            report_path,
        )


if __name__ == "__main__":
    main()
