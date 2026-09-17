"""Keep the runnable simple application compatible with the framework."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestRunConfiguration,
    BacktestWindow,
    CSVOHLCVDataProvider,
    RESOURCE_DIRECTORY,
    SignalSide,
    SnapshotInterval,
    create_app,
)
from investing_algorithm_framework.infrastructure.database import (
    teardown_sqlalchemy,
)


PROJECT_ROOT = Path(__file__).parents[2]
EXAMPLE_PATH = PROJECT_ROOT / "examples" / "simple_app.py"
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "resources"
    / "test_data"
    / "ohlcv"
    / "OHLCV_BTC-EUR_BITVAVO_2h_2021-09-26-08-00_2023-12-02-00-00.csv"
)


def load_simple_app():
    spec = importlib.util.spec_from_file_location("simple_app", EXAMPLE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load example module at {EXAMPLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSimpleAppExample(TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()

    def tearDown(self):
        teardown_sqlalchemy()
        self.temporary_directory.cleanup()

    def test_confluence_strategy_runs_offline_vector_backtest(self):
        simple_app = load_simple_app()
        strategy = simple_app.RSIEMACrossoverStrategy(
            algorithm_id="simple-app-example-test"
        )

        self.assertEqual(
            {
                SignalSide.OPEN_LONG,
                SignalSide.CLOSE_LONG,
                SignalSide.OPEN_SHORT,
                SignalSide.CLOSE_SHORT,
            },
            set(strategy.signal_cards),
        )

        app = create_app(
            name="SimpleAppExampleTest",
            config={RESOURCE_DIRECTORY: self.temporary_directory.name},
        )
        app.add_market(
            market=simple_app.MARKET,
            trading_symbol=simple_app.TRADING_SYMBOL,
            initial_balance=simple_app.INITIAL_CAPITAL,
        )
        app.add_data_provider(
            data_provider=CSVOHLCVDataProvider(
                storage_path=str(FIXTURE_PATH),
                symbol=simple_app.FULL_SYMBOL,
                time_frame="2h",
                market=simple_app.MARKET,
                warmup_window=100,
            ),
            priority=1,
        )

        study = simple_app.create_study(BacktestEngine.VECTOR)
        study.backtest_windows = [
            BacktestWindow(
                name="offline_fixture",
                train_range=BacktestDateRange(
                    start_date=datetime(
                        2023, 9, 1, tzinfo=timezone.utc
                    ),
                    end_date=datetime(
                        2023, 11, 15, tzinfo=timezone.utc
                    ),
                ),
            )
        ]

        results = app.run_backtest(
            strategy=strategy,
            study=study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=(
                    Path(self.temporary_directory.name) / "backtests"
                ),
                snapshot_interval=SnapshotInterval.DAILY,
                use_checkpoints=False,
                show_progress=False,
            ),
        )
        backtest = next(results.iter_backtests())
        completed_study = backtest.get_study(study.name)

        self.assertIsNotNone(completed_study)
        self.assertEqual(["vector"], completed_study.populated_engines())
        self.assertEqual(1, len(completed_study.get_runs(engine="vector")))
        self.assertIsNotNone(completed_study.get_summary(engine="vector"))


if __name__ == "__main__":
    import unittest

    unittest.main()