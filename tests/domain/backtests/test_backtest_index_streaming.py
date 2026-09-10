import gc
import weakref
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import (
    Backtest, BacktestIndex, OperationalException,
)


class TestBacktestIndexStreaming(TestCase):
    def test_open_session_index_without_changing_global_default(self):
        with TemporaryDirectory() as directory:
            pd.DataFrame({"algorithm_id": ["global"]}).to_parquet(
                Path(directory) / "index.parquet",
            )
            pd.DataFrame({"algorithm_id": ["session"]}).to_parquet(
                Path(directory) / "backtest_session_index.parquet",
            )
            self.assertEqual(
                BacktestIndex.open(directory).df["algorithm_id"].tolist(),
                ["global"],
            )
            session = BacktestIndex.open(
                directory, filename="backtest_session_index.parquet",
            )
            self.assertEqual(
                session.df["algorithm_id"].tolist(), ["session"],
            )

    def test_iterator_loads_lazily_and_deduplicates_bundles(self):
        index = BacktestIndex(
            "/unused",
            pd.DataFrame({
                "bundle_path": ["one.obtf", "one.obtf", "two.obtf"],
            }),
        )
        with patch.object(
            Backtest, "open",
            side_effect=lambda path: Backtest(algorithm_id=path.stem),
        ) as load:
            iterator = index.iter_backtests()
            load.assert_not_called()
            first = next(iterator)
            self.assertEqual(first.algorithm_id, "one")
            first_ref = weakref.ref(first)
            del first
            second = next(iterator)
            gc.collect()
            self.assertIsNone(first_ref())
            self.assertEqual(second.algorithm_id, "two")
            with self.assertRaises(StopIteration):
                next(iterator)
            self.assertEqual(load.call_count, 2)

    def test_loading_failure_is_not_silently_skipped(self):
        index = BacktestIndex(
            "/unused", pd.DataFrame({"bundle_path": ["missing.obtf"]}),
        )
        with patch.object(Backtest, "open", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                next(index.iter_backtests())

    def test_eager_loader_deduplicates_pooled_and_universe_rows(self):
        index = BacktestIndex(
            "/unused", pd.DataFrame({
                "bundle_path": ["one.obtf", "one.obtf"],
                "universe_key": [None, "BTC"],
            }),
        )
        with patch(
            "investing_algorithm_framework.domain.backtesting."
            "backtest_utils._open_bundle",
            return_value=Backtest(algorithm_id="one"),
        ) as load:
            results = index.load_backtests(workers=1)
        self.assertEqual(len(results), 1)
        load.assert_called_once()

    def test_invalid_path_is_an_explicit_error(self):
        for dataframe in (
            pd.DataFrame({"algorithm_id": ["one"]}),
            pd.DataFrame({"bundle_path": [None]}),
            pd.DataFrame({"bundle_path": [""]}),
        ):
            with self.subTest(dataframe=dataframe):
                index = BacktestIndex("/unused", dataframe)
                with self.assertRaisesRegex(
                    OperationalException, "bundle_path",
                ):
                    next(index.iter_backtests())

    def test_empty_index_filter_and_iteration(self):
        index = BacktestIndex(
            "/unused", pd.DataFrame(columns=["bundle_path"]),
        )
        filtered = index.filter(lambda row: row["not_present"] > 0)
        self.assertEqual(len(filtered), 0)
        self.assertEqual(list(filtered.iter_backtests()), [])
        self.assertEqual(filtered.df.columns.tolist(), ["bundle_path"])
