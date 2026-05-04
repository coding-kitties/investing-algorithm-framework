"""
Unit tests for content-aware checkpoint manifest hashing and the
checkpoint helpers on BacktestService (issue #276).
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from investing_algorithm_framework import BacktestDateRange
from investing_algorithm_framework.infrastructure import BacktestService
from investing_algorithm_framework.infrastructure.services.backtesting\
    .checkpoint_manifest import (
    algorithm_id_in_entry,
    compute_strategy_manifest_hash,
    get_checkpoint_hash_for_id,
    normalize_checkpoint_entry,
)


class _FakeStrategy:
    """Minimal stand-in for a TradingStrategy used by the manifest hasher."""

    def __init__(self, algorithm_id, params=None, data_sources=None):
        self.algorithm_id = algorithm_id
        self.data_sources = list(data_sources or [])
        if params:
            for k, v in params.items():
                setattr(self, k, v)


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


def _date_range():
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    start = end - timedelta(days=30)
    return BacktestDateRange(start_date=start, end_date=end)


class TestManifestHash(unittest.TestCase):

    def test_hash_is_deterministic(self):
        s = _FakeStrategy("abc", params={"rsi_period": 14, "ema": 200})
        dr = _date_range()
        h1 = compute_strategy_manifest_hash(s, dr)
        h2 = compute_strategy_manifest_hash(s, dr)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)

    def test_hash_changes_when_param_changes(self):
        dr = _date_range()
        s1 = _FakeStrategy("abc", params={"rsi_period": 14})
        s2 = _FakeStrategy("abc", params={"rsi_period": 21})
        self.assertNotEqual(
            compute_strategy_manifest_hash(s1, dr),
            compute_strategy_manifest_hash(s2, dr),
        )

    def test_hash_changes_when_date_range_changes(self):
        s = _FakeStrategy("abc", params={"rsi_period": 14})
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        dr1 = BacktestDateRange(
            start_date=end - timedelta(days=30), end_date=end
        )
        dr2 = BacktestDateRange(
            start_date=end - timedelta(days=60), end_date=end
        )
        self.assertNotEqual(
            compute_strategy_manifest_hash(s, dr1),
            compute_strategy_manifest_hash(s, dr2),
        )

    def test_hash_ignores_algorithm_id(self):
        dr = _date_range()
        s1 = _FakeStrategy("abc", params={"rsi_period": 14})
        s2 = _FakeStrategy("xyz", params={"rsi_period": 14})
        # Same code (same class), same params, same date range,
        # different algorithm_id -> hash must match (algorithm_id is
        # the lookup key, not part of the content fingerprint).
        self.assertEqual(
            compute_strategy_manifest_hash(s1, dr),
            compute_strategy_manifest_hash(s2, dr),
        )


class TestNormalizeCheckpointEntry(unittest.TestCase):

    def test_legacy_list_entry(self):
        result = normalize_checkpoint_entry(["a", "b"])
        self.assertEqual(result, {"a": None, "b": None})

    def test_dict_entry_with_string_hash(self):
        result = normalize_checkpoint_entry({"a": "deadbeef", "b": None})
        self.assertEqual(result, {"a": "deadbeef", "b": None})

    def test_dict_entry_with_nested_dict(self):
        result = normalize_checkpoint_entry(
            {"a": {"manifest_hash": "deadbeef"}}
        )
        self.assertEqual(result, {"a": "deadbeef"})

    def test_unknown_shape_returns_empty(self):
        self.assertEqual(normalize_checkpoint_entry(None), {})
        self.assertEqual(normalize_checkpoint_entry("oops"), {})


class TestEntryHelpers(unittest.TestCase):

    def test_get_checkpoint_hash_for_id_legacy(self):
        self.assertIsNone(get_checkpoint_hash_for_id(["a"], "a"))

    def test_get_checkpoint_hash_for_id_dict(self):
        self.assertEqual(
            get_checkpoint_hash_for_id({"a": "h1"}, "a"), "h1"
        )

    def test_algorithm_id_in_entry(self):
        self.assertTrue(algorithm_id_in_entry(["a", "b"], "a"))
        self.assertTrue(algorithm_id_in_entry({"a": "h"}, "a"))
        self.assertFalse(algorithm_id_in_entry(["a"], "b"))


class TestSelectItemsToRerun(unittest.TestCase):

    def setUp(self):
        self.dr = _date_range()
        self.key = BacktestService._checkpoint_key_for(self.dr)
        self.s_a = _FakeStrategy("a")
        self.s_b = _FakeStrategy("b")
        self.s_c = _FakeStrategy("c")

    def test_no_checkpoints_runs_everything(self):
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a, self.s_b],
            ["a", "b"],
            {"a": "h_a", "b": "h_b"},
            checkpoint_cache={},
            date_range=self.dr,
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(matched, [])
        self.assertEqual(stale, [])

    def test_matching_hash_skips(self):
        cache = {self.key: {"a": "h_a"}}
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a, self.s_b],
            ["a", "b"],
            {"a": "h_a", "b": "h_b"},
            checkpoint_cache=cache,
            date_range=self.dr,
        )
        # 'a' is matched and skipped; 'b' has no checkpoint, runs
        self.assertEqual([s.algorithm_id for s in items], ["b"])
        self.assertEqual(matched, ["a"])
        self.assertEqual(stale, [])

    def test_stale_hash_reruns(self):
        cache = {self.key: {"a": "stale_hash"}}
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a],
            ["a"],
            {"a": "h_a"},
            checkpoint_cache=cache,
            date_range=self.dr,
        )
        self.assertEqual([s.algorithm_id for s in items], ["a"])
        self.assertEqual(matched, [])
        self.assertEqual(stale, ["a"])

    def test_legacy_list_treated_as_match(self):
        # Legacy entries (no hash recorded) preserve the old "skip on
        # algorithm_id match" behaviour.
        cache = {self.key: ["a"]}
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a, self.s_b],
            ["a", "b"],
            {"a": "h_a", "b": "h_b"},
            checkpoint_cache=cache,
            date_range=self.dr,
        )
        self.assertEqual([s.algorithm_id for s in items], ["b"])
        self.assertEqual(matched, ["a"])
        self.assertEqual(stale, [])

    def test_force_rerun_true_runs_everything(self):
        cache = {self.key: {"a": "h_a"}}
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a, self.s_b],
            ["a", "b"],
            {"a": "h_a", "b": "h_b"},
            checkpoint_cache=cache,
            date_range=self.dr,
            force_rerun=True,
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(matched, [])
        self.assertEqual(stale, [])

    def test_on_checkpoint_match_rerun(self):
        cache = {self.key: {"a": "h_a"}}
        items, matched, stale = BacktestService._select_items_to_rerun(
            [self.s_a],
            ["a"],
            {"a": "h_a"},
            checkpoint_cache=cache,
            date_range=self.dr,
            on_checkpoint_match="rerun",
        )
        self.assertEqual([s.algorithm_id for s in items], ["a"])
        self.assertEqual(matched, ["a"])

    def test_get_checkpointed_from_cache_supports_dict(self):
        service = _make_service()
        cache = {self.key: {"a": "h_a", "b": None}}
        ids = service._get_checkpointed_from_cache(cache, self.dr)
        self.assertEqual(sorted(ids), ["a", "b"])

    def test_get_checkpointed_from_cache_supports_list(self):
        service = _make_service()
        cache = {self.key: ["a", "b"]}
        ids = service._get_checkpointed_from_cache(cache, self.dr)
        self.assertEqual(ids, ["a", "b"])


class TestBatchSaveCheckpointFormat(unittest.TestCase):
    """
    Verify that _batch_save_and_checkpoint persists the new dict-format
    when manifest_hashes are provided, and preserves legacy list format
    when they are not.
    """

    def setUp(self):
        self.dr = _date_range()
        self.key = BacktestService._checkpoint_key_for(self.dr)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _service(self):
        return _make_service()

    def _backtest(self, algo_id):
        b = MagicMock()
        b.algorithm_id = algo_id
        return b

    def test_writes_dict_format_with_hashes(self):
        service = self._service()
        # patch save_backtests_to_directory to a no-op so we don't
        # need to materialize backtests on disk
        import investing_algorithm_framework.infrastructure.services\
            .backtesting.backtest_service as bt_mod
        original = bt_mod.save_backtests_to_directory
        bt_mod.save_backtests_to_directory = lambda **kw: None
        try:
            cache = {}
            backtests = [self._backtest("a"), self._backtest("b")]
            service._batch_save_and_checkpoint(
                backtests=backtests,
                date_range=self.dr,
                storage_directory=self.tmp,
                checkpoint_cache=cache,
                manifest_hashes={"a": "h_a", "b": "h_b"},
            )
        finally:
            bt_mod.save_backtests_to_directory = original

        with open(os.path.join(self.tmp, "checkpoints.json")) as f:
            persisted = json.load(f)
        self.assertEqual(
            persisted[self.key], {"a": "h_a", "b": "h_b"}
        )

    def test_migrates_legacy_list_to_dict_when_hashes_given(self):
        service = self._service()
        import investing_algorithm_framework.infrastructure.services\
            .backtesting.backtest_service as bt_mod
        original = bt_mod.save_backtests_to_directory
        bt_mod.save_backtests_to_directory = lambda **kw: None
        try:
            cache = {self.key: ["a"]}  # legacy entry
            service._batch_save_and_checkpoint(
                backtests=[self._backtest("b")],
                date_range=self.dr,
                storage_directory=self.tmp,
                checkpoint_cache=cache,
                manifest_hashes={"b": "h_b"},
            )
        finally:
            bt_mod.save_backtests_to_directory = original

        self.assertEqual(
            cache[self.key], {"a": None, "b": "h_b"}
        )

    def test_preserves_legacy_list_when_no_hashes_given(self):
        service = self._service()
        import investing_algorithm_framework.infrastructure.services\
            .backtesting.backtest_service as bt_mod
        original = bt_mod.save_backtests_to_directory
        bt_mod.save_backtests_to_directory = lambda **kw: None
        try:
            cache = {}
            service._batch_save_and_checkpoint(
                backtests=[self._backtest("a")],
                date_range=self.dr,
                storage_directory=self.tmp,
                checkpoint_cache=cache,
            )
        finally:
            bt_mod.save_backtests_to_directory = original

        self.assertEqual(cache[self.key], ["a"])


if __name__ == "__main__":
    unittest.main()
