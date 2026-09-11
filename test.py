"""Manual showcase script (not part of the pytest suite) for the
in-sample-vector -> select-top-N -> event-validate-a-subset workflow,
and the API additions that make it convenient:

- ``get_backtest(storage_dir, algorithm_id)`` /
  ``get_backtests(storage_dir, algorithm_ids)`` — reload specific
  saved backtests by id, without scanning/ranking the whole directory.
- ``Backtest.get_study_definition(name)`` — pull a single study's
  config (universe, windows, execution assumptions, ...) straight off
  a loaded backtest, reset and ready for a fresh ``run_backtest()``
  call, instead of re-declaring it by hand.
- ``run_backtest(..., backtest_storage_directory=<same dir>)`` merges
  the new engine's results into the SAME ``.obtf`` bundle automatically.

Run directly: `.venv/bin/python test.py`
"""
from investing_algorithm_framework import BacktestRunConfiguration
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from itertools import product

from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy, DataSource, DataType, Schedule, TimeUnit,
    PositionSize, SignalSide, signals_from_column, signal_series_from_column,
    create_app, RESOURCE_DIRECTORY, DATA_DIRECTORY, generate_algorithm_id,
    generate_rolling_backtest_windows, Study, Universe, BacktestEngine,
    StudySampleType, WindowPart, Backtest, get_backtests,
)

REPO_ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = str(REPO_ROOT / "tests" / "resources")
STORAGE_DIR = Path("/tmp/iaf_study_reuse_showcase")
MARKET = "BITVAVO"
SYMBOL = "BTC"
TIME_FRAME = "2h"
IN_SAMPLE_STUDY_NAME = "in_sample_param_sweep"
TOP_N = 10


class RSIEMACrossoverStrategy(TradingStrategy):
    """RSI + EMA crossover, parameterized so a param sweep can be run
    over many (rsi_overbought_threshold, ema_long_period) combos."""

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = [SYMBOL]
    position_sizes = [
        PositionSize(symbol=SYMBOL, percentage_of_portfolio=20.0),
    ]

    def __init__(
        self,
        algorithm_id: str,
        rsi_period: int,
        rsi_overbought_threshold: float,
        rsi_oversold_threshold: float,
        ema_short_period: int,
        ema_long_period: int,
        ema_cross_lookback_window: int = 10,
    ):
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_cross_lookback_window = ema_cross_lookback_window

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=[
                DataSource(
                    identifier=f"{SYMBOL}_ohlcv", data_type=DataType.OHLCV,
                    time_frame=TIME_FRAME, market=MARKET,
                    symbol=f"{SYMBOL}/EUR", pandas=True, warmup_window=200,
                ),
            ],
        )

    def _prepare_indicators(self, df):
        df = ema(
            df, period=self.ema_short_period, source_column="Close",
            result_column=self.ema_short_result_column,
        )
        df = ema(
            df, period=self.ema_long_period, source_column="Close",
            result_column=self.ema_long_result_column,
        )
        df = crossover(
            df, first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column="ema_crossover",
        )
        df = crossunder(
            df, first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column="ema_crossunder",
        )
        df = rsi(
            df, period=self.rsi_period, source_column="Close",
            result_column=self.rsi_result_column,
        )

        crossover_lookback = df["ema_crossover"].rolling(
            window=self.ema_cross_lookback_window,
        ).max().astype(bool)
        crossunder_lookback = df["ema_crossunder"].rolling(
            window=self.ema_cross_lookback_window,
        ).max().astype(bool)

        df["entry"] = (
            (df[self.rsi_result_column] < self.rsi_oversold_threshold)
            & crossover_lookback
        ).fillna(False)
        df["exit"] = (
            (df[self.rsi_result_column] >= self.rsi_overbought_threshold)
            & crossunder_lookback
        ).fillna(False)
        return df

    def generate_signals(self, context, data: Dict[str, Any]):
        df = self._prepare_indicators(data[f"{SYMBOL}_ohlcv"].copy())
        yield from signals_from_column(
            df, "entry", side=SignalSide.OPEN_LONG, symbol=SYMBOL,
        )
        yield from signals_from_column(
            df, "exit", side=SignalSide.CLOSE_LONG, symbol=SYMBOL,
        )

    def generate_signal_series(self, data: Dict[str, Any]):
        df = self._prepare_indicators(data[f"{SYMBOL}_ohlcv"].copy())
        yield signal_series_from_column(
            df, "entry", side=SignalSide.OPEN_LONG, symbol=SYMBOL,
        )
        yield signal_series_from_column(
            df, "exit", side=SignalSide.CLOSE_LONG, symbol=SYMBOL,
        )


def _make_app(name: str):
    config = {
        RESOURCE_DIRECTORY: RESOURCE_DIR, DATA_DIRECTORY: "test_data/ohlcv",
    }
    app = create_app(name=name, config=config)
    app.add_market(market=MARKET, trading_symbol="EUR", initial_balance=1000)
    return app


def main():
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
    STORAGE_DIR.mkdir(parents=True)

    # --- 1. Build the param grid + rolling windows for the vector sweep ---
    param_grid = {
        "rsi_period": [14],
        "rsi_overbought_threshold": [65, 70, 75, 80],
        "rsi_oversold_threshold": [30],
        "ema_short_period": [10, 20],
        "ema_long_period": [50, 80, 120],
    }
    param_variations = [
        dict(zip(param_grid.keys(), values))
        for values in product(*param_grid.values())
    ]
    print(f"Param grid: {len(param_variations)} variants")

    rolling_windows = generate_rolling_backtest_windows(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 11, 1, tzinfo=timezone.utc),
        train_days=90, test_days=90, step_days=90, warmup_days=15,
    )
    print(f"Rolling windows: {len(rolling_windows)}")

    in_sample_study = Study(
        name=IN_SAMPLE_STUDY_NAME,
        description="RSI/EMA crossover param sweep on BTC/EUR (BITVAVO, 2h).",
        risk_free_rate=0.027,
        initial_capital=1000,
        sample_type=StudySampleType.IN_SAMPLE,
        universe=Universe(
            symbols=[SYMBOL], trading_symbol="EUR", market=MARKET,
        ),
        backtest_windows=rolling_windows,
        window_part=WindowPart.TEST,
        engines=[BacktestEngine.VECTOR],
    )

    strategies = [
        RSIEMACrossoverStrategy(
            algorithm_id=generate_algorithm_id(params=variant), **variant,
        )
        for variant in param_variations
    ]

    # --- 2. Vector sweep: fast screening of every param combo, saved ------
    print("\nRunning vector sweep ...")
    app = _make_app("VectorSweep")
    vector_backtests = app.run_backtest(
        strategies=strategies,
        study=in_sample_study,
        run_configuration=BacktestRunConfiguration(
            backtest_storage_directory=str(STORAGE_DIR),
        ),
    )
    print(
        f"Vector sweep produced {len(vector_backtests)} backtests, "
        f"saved to {STORAGE_DIR}"
    )

    # --- 3. Rank by pooled vector CAGR, pick the top 10 -------------------
    # CAGR is derived from the equity curve, so (unlike Sharpe) it stays
    # a well-defined real number even for variants with only 1-2 trades.
    def _cagr(bt: Backtest) -> float:
        study = bt.get_study(IN_SAMPLE_STUDY_NAME)
        summary = study.get_summary("vector") if study else None
        value = summary.cagr if summary else None
        return value if value is not None and value == value else -999.0

    ranked = sorted(vector_backtests, key=_cagr, reverse=True)
    top_10_ids = [bt.algorithm_id for bt in ranked[:TOP_N]]
    print(f"\nTop {len(top_10_ids)} algorithm_ids by vector CAGR:")
    for algo_id in top_10_ids:
        winner = next(b for b in ranked if b.algorithm_id == algo_id)
        print(f"  {algo_id}: cagr={_cagr(winner):.4f}")

    # --- 4. Simulate a fresh process: reload ONLY the top 10 by id --------
    reloaded_top_10 = get_backtests(str(STORAGE_DIR), top_10_ids)
    print(
        f"\nReloaded {len(reloaded_top_10)} of {len(top_10_ids)} "
        f"requested backtests from disk."
    )

    # --- 5. Pull the in-sample study straight off a reloaded backtest -----
    event_study = reloaded_top_10[0].get_study_definition(
        IN_SAMPLE_STUDY_NAME
    )
    assert event_study is not None
    assert event_study.get_runs("vector") == [], \
        "copy should reset engine_results"
    print(
        f"\nRecovered study {event_study.name!r} with "
        f"{len(event_study.backtest_windows)} windows from the "
        f"loaded backtest."
    )

    # Restrict to only the FIRST window, switch to the event engine.
    event_study.backtest_windows = event_study.backtest_windows[:1]
    event_study.engines = [BacktestEngine.EVENT_DRIVEN]

    # --- 6. Event-validate the top 10, merged back into the SAME bundles --
    top_10_strategies = [
        s for s in strategies if s.algorithm_id in set(top_10_ids)
    ]
    print(
        f"\nRunning event backtest for {len(top_10_strategies)} strategies "
        f"on window 1 of {len(rolling_windows)} only ..."
    )
    app2 = _make_app("EventValidation")
    event_backtests = app2.run_backtest(
        strategies=top_10_strategies,
        study=event_study,
        run_configuration=BacktestRunConfiguration(
            backtest_storage_directory=str(STORAGE_DIR),
        ),
    )
    print(f"Event validation produced {len(event_backtests)} backtests.")

    # --- 7. Reload once more and confirm both engines share the bundle ----
    reloaded = get_backtests(str(STORAGE_DIR), top_10_ids)
    for bt in reloaded:
        study = bt.get_study(IN_SAMPLE_STUDY_NAME)
        n_vector = len(study.get_runs("vector"))
        n_event = len(study.get_runs("event"))
        n_windows = len(study.backtest_windows)
        print(
            f"  {bt.algorithm_id}: vector_runs={n_vector} "
            f"event_runs={n_event} windows_catalogue={n_windows}"
        )
        assert n_vector == len(rolling_windows)
        assert n_event == 1

    print(
        "\nOK — vector + event results for the top 10 all live in the "
        "same .obtf files."
    )


if __name__ == "__main__":
    main()
