"""Regression tests for `run_backtest(algorithms=...)` with the
vector engine.

Each `Algorithm` in `algorithms=` gets its own portfolio (mirrors
`strategies=`), so multiple single-strategy Algorithms should be able
to run on the vector engine just like plain `strategies=` would. What
genuinely isn't supported is (a) an Algorithm that itself combines more
than one strategy onto a shared portfolio, and (b) an Algorithm with
tasks/hooks registered, since the vector engine only ever consumes the
flattened strategy list and would silently drop those.
"""
import os
from datetime import timezone, datetime
from pathlib import Path
from typing import Dict, Any
from unittest import TestCase
from uuid import uuid4

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, Algorithm, BacktestDateRange, Schedule, TimeUnit, \
    Study, Universe, BacktestWindow, BacktestEngine, Task, \
    OperationalException, CSVOHLCVDataProvider, DataSource, DataType

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
START = datetime(2020, 12, 20, 10, tzinfo=timezone.utc)
END = datetime(2020, 12, 21, 6, tzinfo=timezone.utc)


class VectorTestStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    market = "BITVAVO"
    symbols = ["BTC"]

    def __init__(self, algorithm_id):
        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=[
                DataSource(
                    identifier="BTC_EUR_OHLCV",
                    data_type=DataType.OHLCV,
                    time_frame="2h",
                    market="BITVAVO",
                    symbol="BTC/EUR",
                    warmup_window=5,
                    pandas=True,
                )
            ],
        )

    def generate_signal_series(self, data: Dict[str, Any]):
        return iter(())


class NoOpTask(Task):
    schedule = Schedule.every(1, TimeUnit.MINUTE)

    def run(self, algorithm):
        pass


class TestIndependentAlgorithmsVectorEngine(TestCase):
    def setUp(self) -> None:
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "resources"
        )

    def _app(self):
        app = create_app(
            name=f"VectorIndependentAlgorithms{uuid4().hex}",
            config={RESOURCE_DIRECTORY: self.resource_dir},
        )
        app.add_market(market="BITVAVO", trading_symbol="EUR")
        csv_path = Path(self.resource_dir) / "test_data" / "ohlcv" \
            / CSV_FILENAME
        app.add_data_provider(
            data_provider=CSVOHLCVDataProvider(
                storage_path=str(csv_path),
                symbol="BTC/EUR",
                time_frame="2h",
                market="BITVAVO",
                warmup_window=5,
            ),
            priority=1,
        )
        return app

    def _study(self):
        return Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            initial_capital=1000,
            risk_free_rate=0.027,
            backtest_windows=[
                BacktestWindow(
                    train_range=BacktestDateRange(
                        start_date=START, end_date=END
                    )
                )
            ],
            engines=[BacktestEngine.VECTOR],
        )

    def test_single_strategy_algorithms_allowed_with_vector_engine(self):
        app = self._app()
        algorithm_one = Algorithm(
            algorithm_id="algo_one",
            strategy=VectorTestStrategy(algorithm_id="algo_one"),
        )
        algorithm_two = Algorithm(
            algorithm_id="algo_two",
            strategy=VectorTestStrategy(algorithm_id="algo_two"),
        )

        backtests = app.run_backtest(
            algorithms=[algorithm_one, algorithm_two], study=self._study()
        )

        self.assertEqual(2, backtests.df["algorithm_id"].nunique())

    def test_multi_strategy_algorithm_rejected_with_vector_engine(self):
        app = self._app()
        strategy_a = VectorTestStrategy(algorithm_id="algo_multi")
        strategy_a.strategy_id = "strategy_a"
        strategy_b = VectorTestStrategy(algorithm_id="algo_multi")
        strategy_b.strategy_id = "strategy_b"
        algorithm = Algorithm(
            algorithm_id="algo_multi",
            strategies=[strategy_a, strategy_b],
        )

        with self.assertRaises(OperationalException) as ctx:
            app.run_backtest(algorithms=[algorithm], study=self._study())

        self.assertIn("shared portfolio", str(ctx.exception))

    def test_algorithm_with_tasks_rejected_with_vector_engine(self):
        app = self._app()
        algorithm = Algorithm(
            algorithm_id="algo_tasks",
            strategy=VectorTestStrategy(algorithm_id="algo_tasks"),
            tasks=[NoOpTask],
        )

        with self.assertRaises(OperationalException) as ctx:
            app.run_backtest(algorithms=[algorithm], study=self._study())

        self.assertIn("tasks/hooks", str(ctx.exception))
