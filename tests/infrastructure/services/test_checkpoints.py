import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from investing_algorithm_framework import BacktestDateRange
from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework.infrastructure import BacktestService


class _FakeStrategy:
    def __init__(self, algorithm_id):
        self.algorithm_id = algorithm_id


def _make_service():
    return BacktestService(
        data_provider_service=MagicMock(),
        order_service=MagicMock(),
        portfolio_service=MagicMock(),
        portfolio_snapshot_service=MagicMock(),
        position_repository=MagicMock(),
        trade_service=MagicMock(),
        configuration_service=MagicMock(),
        portfolio_configuration_service=MagicMock(),
    )


def _date_range(offset_days=0):
    end = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=offset_days
    )
    return BacktestDateRange(
        start_date=end - timedelta(days=30),
        end_date=end,
    )


class TestCheckpointSelection(unittest.TestCase):

    def setUp(self):
        self.first_window = _date_range()
        self.second_window = _date_range(30)
        self.strategy_a = _FakeStrategy("a")
        self.strategy_b = _FakeStrategy("b")

    def test_resume_skips_completed_window_and_runs_next_window(self):
        cache = {
            BacktestService._checkpoint_key_for(self.first_window): {"a", "b"}
        }

        first_items, first_matches = (
            BacktestService._select_items_to_rerun(
                [self.strategy_a, self.strategy_b],
                ["a", "b"],
                cache,
                self.first_window,
            )
        )
        second_items, second_matches = (
            BacktestService._select_items_to_rerun(
                [self.strategy_a, self.strategy_b],
                ["a", "b"],
                cache,
                self.second_window,
            )
        )

        self.assertEqual(first_items, [])
        self.assertEqual(first_matches, ["a", "b"])
        self.assertEqual(second_items, [self.strategy_a, self.strategy_b])
        self.assertEqual(second_matches, [])

    def test_algorithm_id_is_the_only_strategy_identity(self):
        replacement = _FakeStrategy("a")
        replacement.changed_parameter = object()
        cache = {
            BacktestService._checkpoint_key_for(self.first_window): {"a"}
        }

        items, matches = BacktestService._select_items_to_rerun(
            [replacement],
            ["a"],
            cache,
            self.first_window,
        )

        self.assertEqual(items, [])
        self.assertEqual(matches, ["a"])

    def test_force_rerun_runs_all_items(self):
        cache = {
            BacktestService._checkpoint_key_for(self.first_window): {"a"}
        }

        items, matches = BacktestService._select_items_to_rerun(
            [self.strategy_a, self.strategy_b],
            ["a", "b"],
            cache,
            self.first_window,
            force_rerun=True,
        )

        self.assertEqual(items, [self.strategy_a, self.strategy_b])
        self.assertEqual(matches, [])

    def test_missing_window_runs_all_items(self):
        items, matches = BacktestService._select_items_to_rerun(
            [self.strategy_a, self.strategy_b], ["a", "b"],
            {}, self.first_window,
        )

        self.assertEqual(items, [self.strategy_a, self.strategy_b])
        self.assertEqual(matches, [])

    def test_checkpoint_matches_do_not_include_unrequested_algorithms(self):
        cache = {
            BacktestService._checkpoint_key_for(self.first_window):
                {"a", "not-requested"}
        }
        items, matches = BacktestService._select_items_to_rerun(
            [self.strategy_a, self.strategy_b], ["a", "b"],
            cache, self.first_window,
        )

        self.assertEqual(items, [self.strategy_b])
        self.assertEqual(matches, ["a"])

    def test_500_completed_ids_are_skipped_without_inspecting_strategies(self):
        ids = [f"algorithm-{i}" for i in range(500)]
        items, matches = BacktestService._select_items_to_rerun(
            [object() for _ in ids], ids,
            {BacktestService._checkpoint_key_for(self.first_window): set(ids)},
            self.first_window,
        )

        self.assertEqual(items, [])
        self.assertEqual(matches, ids)


class TestCheckpointPersistence(unittest.TestCase):

    def setUp(self):
        self.service = _make_service()
        self.date_range = _date_range()
        self.key = BacktestService._checkpoint_key_for(self.date_range)
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    @patch(
        "investing_algorithm_framework.infrastructure.services.backtesting."
        "backtest_service.save_backtests_to_directory"
    )
    def test_batch_save_writes_v9_id_list(self, save_backtests):
        backtest = MagicMock()
        backtest.algorithm_id = "algorithm-a"
        cache = {}

        self.service._batch_save_and_checkpoint(
            [backtest],
            self.date_range,
            self.directory.name,
            cache,
        )

        with open(
            os.path.join(self.directory.name, "checkpoints.json")
        ) as checkpoint_file:
            persisted = json.load(checkpoint_file)

        self.assertEqual(cache, {self.key: {"algorithm-a"}})
        self.assertEqual(persisted, {self.key: ["algorithm-a"]})
        save_backtests.assert_called_once()

    def test_load_uses_sets_for_constant_time_membership(self):
        checkpoint_file = os.path.join(
            self.directory.name, "checkpoints.json"
        )
        with open(checkpoint_file, "w") as handle:
            json.dump({self.key: ["a", "b"]}, handle)

        cache = self.service._load_checkpoint_cache(self.directory.name)

        self.assertEqual(cache, {self.key: {"a", "b"}})

    def test_load_rejects_pre_v9_hash_entries(self):
        checkpoint_file = os.path.join(
            self.directory.name, "checkpoints.json"
        )
        with open(checkpoint_file, "w") as handle:
            json.dump({self.key: {"a": "manifest-hash"}}, handle)

        with self.assertRaisesRegex(
            OperationalException,
            "each window must map to a list of algorithm IDs",
        ):
            self.service._load_checkpoint_cache(self.directory.name)

    def test_missing_checkpoint_file_returns_empty_cache(self):
        self.assertEqual(
            self.service._load_checkpoint_cache(self.directory.name), {},
        )

    def test_invalid_checkpoint_shapes_are_not_silently_ignored(self):
        checkpoint_file = os.path.join(
            self.directory.name, "checkpoints.json",
        )
        for invalid in ([], None, {self.key: "a"}, {self.key: [1]}):
            with self.subTest(checkpoint=invalid):
                with open(checkpoint_file, "w") as handle:
                    json.dump(invalid, handle)

                with self.assertRaises(OperationalException):
                    self.service._load_checkpoint_cache(self.directory.name)

    @patch(
        "investing_algorithm_framework.infrastructure.services.backtesting."
        "backtest_service.save_backtests_to_directory"
    )
    def test_repeated_saves_deduplicate_ids_and_preserve_other_windows(
        self, save_backtests,
    ):
        other_key = BacktestService._checkpoint_key_for(_date_range(30))
        cache = {self.key: {"a"}, other_key: {"other"}}
        backtests = [
            _FakeStrategy("a"), _FakeStrategy("b"), _FakeStrategy("b"),
        ]

        self.service._batch_save_and_checkpoint(
            backtests, self.date_range, self.directory.name, cache,
        )

        with open(
            os.path.join(self.directory.name, "checkpoints.json"),
        ) as handle:
            self.assertEqual(
                json.load(handle),
                {self.key: ["a", "b"], other_key: ["other"]},
            )
        self.assertEqual(
            self.service._load_checkpoint_cache(self.directory.name),
            {self.key: {"a", "b"}, other_key: {"other"}},
        )

    @patch(
        "investing_algorithm_framework.infrastructure.services.backtesting."
        "backtest_service.save_backtests_to_directory"
    )
    def test_failed_atomic_replace_preserves_last_durable_checkpoint(
        self, save_backtests,
    ):
        checkpoint_file = os.path.join(
            self.directory.name, "checkpoints.json",
        )
        with open(checkpoint_file, "w") as handle:
            json.dump({self.key: ["a"]}, handle)
        cache = self.service._load_checkpoint_cache(self.directory.name)

        with patch(
            "investing_algorithm_framework.infrastructure.services."
            "backtesting.backtest_service.os.replace",
            side_effect=OSError("simulated checkpoint write failure"),
        ), self.assertRaisesRegex(OSError, "checkpoint write failure"):
            self.service._batch_save_and_checkpoint(
                [_FakeStrategy("b")], self.date_range,
                self.directory.name, cache,
            )

        self.assertEqual(
            self.service._load_checkpoint_cache(self.directory.name),
            {self.key: {"a"}},
        )
        self.assertFalse(os.path.exists(checkpoint_file + ".pending"))


if __name__ == "__main__":
    unittest.main()
