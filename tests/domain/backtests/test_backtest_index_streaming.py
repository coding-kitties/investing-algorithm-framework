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
    def test_persist_session_index_uses_writable_flush_handle(self):
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.vector_session_index import (
                persist_index, SESSION_INDEX_FILENAME,
            )

        original_open = Path.open
        flush_handles = []

        def track_open(path, mode="r", *args, **kwargs):
            handle = original_open(path, mode, *args, **kwargs)
            if path.suffix == ".pending":
                flush_handles.append(handle)
                self.assertTrue(handle.writable())
            return handle

        with TemporaryDirectory() as directory:
            index = BacktestIndex(
                directory, pd.DataFrame({"algorithm_id": ["saved"]}),
            )
            with patch.object(Path, "open", track_open):
                persist_index(index)
            self.assertEqual(len(flush_handles), 1)
            self.assertTrue(flush_handles[0].closed)
            pd.testing.assert_frame_equal(
                pd.read_parquet(Path(directory) / SESSION_INDEX_FILENAME),
                index.df,
            )
            self.assertEqual(list(Path(directory).glob("*.pending")), [])

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


class TestBacktestIndexLookup(TestCase):
    def setUp(self):
        self.index = BacktestIndex(
            "/unused",
            pd.DataFrame({
                "algorithm_id": ["one", "one", "two"],
                "bundle_path": [
                    "nested/custom-name.obtf", "nested/custom-name.obtf",
                    "two.obtf",
                ],
            }),
        )

    def test_get_backtest_loads_only_the_indexed_bundle_once(self):
        expected = Backtest(algorithm_id="one")
        original = self.index.df.copy(deep=True)
        with patch.object(Backtest, "open", return_value=expected) as load:
            self.assertIs(self.index.get_backtest("one"), expected)
        load.assert_called_once_with(
            Path("/unused/nested/custom-name.obtf"),
        )
        pd.testing.assert_frame_equal(self.index.df, original)

    def test_missing_and_filtered_out_algorithms_do_not_load_bundles(self):
        filtered = self.index.filter(lambda row: row["algorithm_id"] == "two")
        with patch.object(Backtest, "open") as load:
            self.assertIsNone(self.index.get_backtest("missing"))
            self.assertIsNone(filtered.get_backtest("one"))
            self.assertIsNone(
                BacktestIndex("/unused", pd.DataFrame()).get_backtest("one"),
            )
        load.assert_not_called()

    def test_loading_failure_propagates(self):
        with patch.object(Backtest, "open", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                self.index.get_backtest("one")

    def test_ambiguous_bundle_paths_raise_before_loading(self):
        self.index.df.loc[1, "bundle_path"] = "different.obtf"
        with patch.object(Backtest, "open") as load:
            with self.assertRaisesRegex(
                OperationalException, "multiple bundles",
            ):
                self.index.get_backtest("one")
        load.assert_not_called()

    def test_invalid_index_columns_and_paths_raise_explicit_errors(self):
        for frame, message in (
            (pd.DataFrame({"bundle_path": ["one.obtf"]}), "algorithm_id"),
            (pd.DataFrame({"algorithm_id": ["one"]}), "bundle_path"),
            (pd.DataFrame({
                "algorithm_id": ["one"], "bundle_path": [None],
            }), "bundle_path"),
            (pd.DataFrame({
                "algorithm_id": ["one"], "bundle_path": [""],
            }), "bundle_path"),
        ):
            with self.subTest(frame=frame), self.assertRaisesRegex(
                OperationalException, message,
            ):
                BacktestIndex("/unused", frame).get_backtest("one")

    def test_reopened_index_supports_lookup(self):
        with TemporaryDirectory() as directory:
            self.index.df.to_parquet(Path(directory) / "index.parquet")
            reopened = BacktestIndex.open(directory)
            expected = Backtest(algorithm_id="one")
            with patch.object(
                Backtest, "open", return_value=expected,
            ) as load:
                self.assertIs(reopened.get_backtest("one"), expected)
            load.assert_called_once_with(
                Path(directory) / "nested/custom-name.obtf",
            )


class TestBacktestIndexMetadata(TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "algorithm_id": ["beta", "alpha", "alpha", "alpha", "beta"],
            "study_name": [
                "validation", "train", "train", "validation", "train",
            ],
            "engine_type": ["event", "vector", "vector", "event", "vector"],
            "universe_key": [None, None, "BTC", "ETH", "BTC"],
        })
        self.index = BacktestIndex("/unused", self.frame)

    def test_distinct_identifiers_are_sorted_and_deduplicated(self):
        self.assertEqual(self.index.get_algorithm_ids(), ["alpha", "beta"])
        self.assertEqual(self.index.get_study_names(), ["train", "validation"])
        self.assertEqual(self.index.get_engine_types(), ["event", "vector"])
        self.assertEqual(self.index.get_universe_keys(), ["BTC", "ETH"])

    def test_summary_counts_entities_not_rows_or_bundles(self):
        with patch.object(
            Backtest, "open",
            side_effect=AssertionError("Metadata must not load bundles"),
        ) as load:
            self.assertEqual(self.index.get_summary(), {
                "number_of_rows": 5,
                "number_of_algorithms": 2,
                "number_of_studies": 2,
                "number_of_engines": 2,
                "number_of_universes": 2,
            })
        load.assert_not_called()
        self.assertEqual(len(self.index), 5)

    def test_filtered_index_reports_only_remaining_entities(self):
        filtered = self.index.filter(
            lambda row: row["study_name"] == "validation",
        )
        self.assertEqual(filtered.get_summary(), {
            "number_of_rows": 2,
            "number_of_algorithms": 2,
            "number_of_studies": 1,
            "number_of_engines": 1,
            "number_of_universes": 1,
        })
        self.assertEqual(filtered.get_study_names(), ["validation"])
        self.assertEqual(self.index.get_number_of_studies(), 2)

    def test_empty_indexes_have_empty_identifiers_and_zero_counts(self):
        for frame in (pd.DataFrame(), self.frame.iloc[:0]):
            with self.subTest(columns=frame.columns.tolist()):
                index = BacktestIndex("/unused", frame)
                self.assertEqual(index.get_algorithm_ids(), [])
                self.assertEqual(index.get_study_names(), [])
                self.assertEqual(index.get_engine_types(), [])
                self.assertEqual(index.get_universe_keys(), [])
                self.assertEqual(index.get_summary(), {
                    "number_of_rows": 0,
                    "number_of_algorithms": 0,
                    "number_of_studies": 0,
                    "number_of_engines": 0,
                    "number_of_universes": 0,
                })
        self.assertEqual(
            self.index.filter(lambda row: False).get_number_of_algorithms(), 0,
        )

    def test_null_identifiers_are_not_counted(self):
        frame = pd.DataFrame({
            column: [None, pd.NA, float("nan"), "recorded", "recorded"]
            for column in self.frame.columns
        })
        index = BacktestIndex("/unused", frame)
        self.assertEqual(index.get_summary(), {
            "number_of_rows": 5,
            "number_of_algorithms": 1,
            "number_of_studies": 1,
            "number_of_engines": 1,
            "number_of_universes": 1,
        })
        self.assertEqual(index.get_algorithm_ids(), ["recorded"])
        index.df.loc[:, "universe_key"] = None
        self.assertEqual(index.get_number_of_universes(), 0)
        self.assertEqual(index.get_universe_keys(), [])

    def test_counts_follow_dataframe_changes_and_lists_are_independent(self):
        identifiers = self.index.get_algorithm_ids()
        identifiers.append("not-in-index")
        self.assertEqual(self.index.get_number_of_algorithms(), 2)
        self.index.df.loc[0, "algorithm_id"] = "gamma"
        self.assertEqual(
            self.index.get_algorithm_ids(), ["alpha", "beta", "gamma"],
        )
        self.assertEqual(self.index.get_number_of_algorithms(), 3)

    def test_missing_columns_raise_explicit_errors_for_nonempty_indexes(self):
        for column in self.frame.columns:
            index = BacktestIndex("/unused", self.frame.drop(columns=column))
            with self.subTest(column=column), self.assertRaisesRegex(
                OperationalException, column,
            ):
                index.get_summary()

    def test_invalid_identifier_types_raise_explicit_errors(self):
        for column in self.frame.columns:
            frame = self.frame.copy()
            frame[column] = frame[column].astype(object)
            frame.loc[0, column] = 42
            index = BacktestIndex("/unused", frame)
            with self.subTest(column=column), self.assertRaisesRegex(
                OperationalException, f"{column} values must be strings",
            ):
                index.get_summary()

    def test_reopened_index_preserves_metadata_counts(self):
        with TemporaryDirectory() as directory:
            self.frame.to_parquet(Path(directory) / "index.parquet")
            reopened = BacktestIndex.open(directory)
            self.assertEqual(reopened.get_summary(), self.index.get_summary())
            self.assertEqual(
                reopened.get_algorithm_ids(), self.index.get_algorithm_ids(),
            )
