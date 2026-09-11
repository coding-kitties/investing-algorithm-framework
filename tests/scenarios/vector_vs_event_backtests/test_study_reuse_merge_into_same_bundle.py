"""
Regression test for the "vector sweep -> reuse the study straight off
a loaded backtest -> event-validate a window subset -> merge back into
the SAME .obtf bundle" workflow, and the ``get_backtest()`` /
``get_backtests()`` / ``Backtest.get_study_definition()`` convenience
API that supports it.
"""
from investing_algorithm_framework import BacktestRunConfiguration
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import (
    TradingStrategy, DataSource, DataType, TimeUnit, Schedule,
    PositionSize, SignalSide, SignalSeries, signals_from_column,
    create_app, RESOURCE_DIRECTORY, CSVOHLCVDataProvider,
    BacktestDateRange, BacktestWindow, BacktestEngine, Study, Universe,
    StudySampleType, get_backtest, get_backtests,
)

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv"
WARMUP = 5
STUDY_NAME = "in_sample_param_sweep"
ALGORITHM_ID = "study_reuse_merge_test"


def _make_data_source():
    return DataSource(
        symbol="BTC/EUR", data_type=DataType.OHLCV, time_frame="2h",
        warmup_window=WARMUP, market="BITVAVO",
        identifier="BTC_EUR_OHLCV", pandas=True,
    )


class SimpleBuySellStrategy(TradingStrategy):
    """Buy at Close==110, sell at Close==90 (deterministic fixture)."""

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [PositionSize(symbol="BTC", percentage_of_portfolio=20.0)]

    def generate_signals(self, context, data):
        df = data["BTC_EUR_OHLCV"].copy()
        df["buy"] = df['Close'] == 110
        df["sell"] = df['Close'] == 90
        yield from signals_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "sell", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )

    def generate_signal_series(self, data):
        df = data["BTC_EUR_OHLCV"]
        yield SignalSeries(
            symbol="BTC", side=SignalSide.OPEN_LONG,
            series=df['Close'] == 110,
        )
        yield SignalSeries(
            symbol="BTC", side=SignalSide.CLOSE_LONG,
            series=df['Close'] == 90,
        )


class TestStudyReuseMergeIntoSameBundle(TestCase):
    """Single strategy, vector sweep (2 windows) then event validation
    (1 window), both landing in the same ``<algorithm_id>.obtf``."""

    def setUp(self):
        self.resource_directory = str(
            Path(__file__).resolve().parents[2] / "resources"
        )
        self.storage_dir = Path(self.resource_directory) / \
            "backtest_reports_for_testing" / "study_reuse_merge_test"
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)
        self.storage_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.storage_dir, ignore_errors=True)

    def _make_app(self, name):
        app = create_app(
            name=name, config={RESOURCE_DIRECTORY: self.resource_directory},
        )
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000,
        )
        app.add_data_provider(
            data_provider=CSVOHLCVDataProvider(
                storage_path=os.path.join(
                    self.resource_directory, "test_data", "ohlcv",
                    CSV_FILENAME,
                ),
                symbol="BTC/EUR", time_frame="2h", market="BITVAVO",
                warmup_window=WARMUP,
            ),
            priority=1,
        )
        return app

    def test_event_validation_merges_into_same_bundle_as_vector_sweep(self):
        window_1 = BacktestWindow(train_range=BacktestDateRange(
            start_date=datetime(2020, 12, 20, 10, 0, tzinfo=timezone.utc),
            end_date=datetime(2020, 12, 20, 22, 0, tzinfo=timezone.utc),
        ))
        window_2 = BacktestWindow(train_range=BacktestDateRange(
            start_date=datetime(2020, 12, 21, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2020, 12, 21, 22, 0, tzinfo=timezone.utc),
        ))

        in_sample_study = Study(
            name=STUDY_NAME,
            risk_free_rate=0.027,
            initial_capital=1000,
            sample_type=StudySampleType.IN_SAMPLE,
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[window_1, window_2],
            engines=[BacktestEngine.VECTOR],
        )

        # --- 1. Vector sweep over both windows, saved to disk ----------
        vector_app = self._make_app("VectorSweep")
        vector_backtests = vector_app.run_backtest(
            strategy=SimpleBuySellStrategy(algorithm_id=ALGORITHM_ID),
            study=in_sample_study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=str(self.storage_dir),
            ),
        )

        bundle_path = self.storage_dir / f"{ALGORITHM_ID}.obtf"
        self.assertTrue(bundle_path.is_file())

        vector_study = next(
            vector_backtests.iter_backtests()
        ).get_study(STUDY_NAME)
        self.assertEqual(2, len(vector_study.get_runs("vector")))

        # --- 2. Reload by id and pull the study definition straight off
        # the loaded backtest, instead of re-declaring it by hand -------
        loaded = get_backtest(str(self.storage_dir), ALGORITHM_ID)
        self.assertIsNotNone(loaded)
        event_study = loaded.get_study_definition(STUDY_NAME)
        self.assertIsNotNone(event_study)
        self.assertEqual([], event_study.get_runs("vector"))
        self.assertEqual(2, len(event_study.backtest_windows))

        # Restrict to only the first window, switch to the event engine.
        event_study.backtest_windows = event_study.backtest_windows[:1]
        event_study.engines = [BacktestEngine.EVENT_DRIVEN]

        # --- 3. Event-validate, saved to the SAME storage directory -----
        event_app = self._make_app("EventValidation")
        event_app.run_backtest(
            strategy=SimpleBuySellStrategy(algorithm_id=ALGORITHM_ID),
            study=event_study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=str(self.storage_dir),
            ),
        )

        # Still exactly one bundle file for this algorithm_id -- the
        # event run merged in rather than creating a second file.
        obtf_files = list(self.storage_dir.glob("*.obtf"))
        self.assertEqual([bundle_path], obtf_files)

        # --- 4. Reload and confirm both engines share the same study ----
        reloaded = get_backtests(str(self.storage_dir), [ALGORITHM_ID])
        self.assertEqual(1, len(reloaded))
        merged_study = reloaded[0].get_study(STUDY_NAME)
        self.assertEqual(2, len(merged_study.get_runs("vector")))
        self.assertEqual(1, len(merged_study.get_runs("event")))
        # Regression check: the window catalogue stays a superset even
        # though the event run only covered window_1.
        self.assertEqual(2, len(merged_study.backtest_windows))
