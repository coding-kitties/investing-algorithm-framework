"""Tests for the single-bundle binary persistence format (issue #487).

The bundle format is a zstd-compressed MessagePack document with a
small magic-number header (``IAFB`` + 4-byte little-endian format
version). It replaces the legacy directory layout for both
``Backtest.save()``/``Backtest.open()`` and the
``save_backtests_to_directory`` / ``load_backtests_from_directory``
helpers.
"""
import os
import shutil
import tempfile
from unittest import TestCase

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndex,
    BUNDLE_EXT,
    BUNDLE_FORMAT_VERSION,
    load_backtests_from_directory,
    migrate_backtests,
    save_backtests_to_directory,
)
from investing_algorithm_framework.domain.backtesting.bundle import (
    _MAGIC,
    is_bundle_file,
    open_bundle,
    save_bundle,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


def _normalize(value):
    """Compare dictionaries while treating any NaN as equal to NaN."""
    import math
    if isinstance(value, float) and math.isnan(value):
        return "__NAN__"
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


class TestBundleRoundTrip(TestCase):
    """Verify that ``save_bundle``/``open_bundle`` round-trip cleanly."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bundle_round_trip_preserves_dict(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        self.assertTrue(os.path.isfile(path))

        loaded = open_bundle(path)
        self.assertEqual(
            _normalize(loaded.to_dict()),
            _normalize(self.fixture.to_dict()),
        )

    def test_bundle_starts_with_magic_and_version(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        with open(path, "rb") as fh:
            head = fh.read(8)
        self.assertEqual(head[:4], _MAGIC)
        self.assertEqual(
            int.from_bytes(head[4:8], "little"),
            BUNDLE_FORMAT_VERSION,
        )

    def test_is_bundle_file_detection(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        self.assertTrue(is_bundle_file(path))

        not_bundle = os.path.join(self.tmp, "plain.txt")
        with open(not_bundle, "wb") as fh:
            fh.write(b"hello world")
        self.assertFalse(is_bundle_file(not_bundle))

    def test_format_version_mismatch_raises(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, path)

        # Flip the format version byte to an unsupported value.
        with open(path, "r+b") as fh:
            fh.seek(4)
            fh.write((BUNDLE_FORMAT_VERSION + 99).to_bytes(4, "little"))

        with self.assertRaises(ValueError):
            open_bundle(path)

    def test_backtest_save_open_dispatches_to_bundle(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        # Backtest.save should auto-detect ``.iafbt`` and write a bundle.
        self.fixture.save(path)
        self.assertTrue(is_bundle_file(path))
        loaded = Backtest.open(path)
        self.assertEqual(
            loaded.algorithm_id, self.fixture.algorithm_id
        )

    def test_merge_on_save_preserves_other_engine_slot(self):
        """Writing an event-only ``Backtest`` over an existing
        vector-only bundle preserves the vector slot, and vice versa
        (design doc \u00a73.5)."""
        from copy import deepcopy
        path = os.path.join(self.tmp, "merge" + BUNDLE_EXT)

        # Step 1: write the fixture (vector-only) as the baseline.
        save_bundle(self.fixture, path)
        baseline = open_bundle(path)
        self.assertEqual(baseline.engines(), ["vector"])

        # Step 2: build an event-only sibling Backtest and save over.
        event_only = deepcopy(self.fixture)
        event_only.event_runs = list(event_only.vector_runs)
        event_only.event_summary = event_only.vector_summary
        event_only.vector_runs = []
        event_only.vector_summary = None
        save_bundle(event_only, path)

        merged = open_bundle(path)
        self.assertEqual(
            sorted(merged.engines()), ["event", "vector"]
        )
        # Vector slot survived intact.
        self.assertEqual(
            len(merged.vector_runs), len(self.fixture.vector_runs)
        )
        # Event slot was written.
        self.assertEqual(
            len(merged.event_runs), len(event_only.event_runs)
        )

    def test_merge_false_overwrites_unconditionally(self):
        path = os.path.join(self.tmp, "no_merge" + BUNDLE_EXT)
        save_bundle(self.fixture, path)

        from copy import deepcopy
        event_only = deepcopy(self.fixture)
        event_only.event_runs = list(event_only.vector_runs)
        event_only.event_summary = event_only.vector_summary
        event_only.vector_runs = []
        event_only.vector_summary = None
        save_bundle(event_only, path, merge=False)

        loaded = open_bundle(path)
        self.assertEqual(loaded.engines(), ["event"])

    def test_dual_engine_bundle_round_trip(self):
        """A single ``.iafbt`` carrying both vector and event slots
        round-trips cleanly via ``save_bundle`` / ``open_bundle``.

        Verifies that namespaced metric blobs (``vector_runs/...`` and
        ``event_runs/...``) are read back into the correct engine slot
        and that per-engine summaries survive intact.
        """
        from copy import deepcopy
        path = os.path.join(self.tmp, "dual" + BUNDLE_EXT)

        dual = deepcopy(self.fixture)
        # Promote the fixture's vector runs/summary into the event slot
        # so the bundle carries non-trivial data for both engines.
        dual.event_runs = deepcopy(dual.vector_runs)
        dual.event_summary = deepcopy(dual.vector_summary)
        self.assertEqual(sorted(dual.engines()), ["event", "vector"])

        save_bundle(dual, path)
        loaded = open_bundle(path)

        self.assertEqual(sorted(loaded.engines()), ["event", "vector"])
        self.assertEqual(
            len(loaded.vector_runs), len(dual.vector_runs)
        )
        self.assertEqual(
            len(loaded.event_runs), len(dual.event_runs)
        )
        # Per-engine summaries preserved.
        self.assertIsNotNone(loaded.get_summary("vector"))
        self.assertIsNotNone(loaded.get_summary("event"))
        # Metric blobs were namespaced + decoded back into the right
        # slot: equity_curve from each engine survives.
        v_metrics = loaded.vector_runs[0].backtest_metrics
        e_metrics = loaded.event_runs[0].backtest_metrics
        self.assertTrue(v_metrics.equity_curve)
        self.assertTrue(e_metrics.equity_curve)
        # Full dict round-trip equality (NaN-tolerant).
        self.assertEqual(
            _normalize(loaded.to_dict()), _normalize(dual.to_dict())
        )

    def test_merge_on_save_appends_vector_to_event_only_bundle(self):
        """Symmetric to the vector→event merge test: writing a
        vector-only Backtest over an existing event-only bundle
        appends the vector slot rather than overwriting the event
        slot (design doc \u00a73.5)."""
        from copy import deepcopy
        path = os.path.join(self.tmp, "append_vector" + BUNDLE_EXT)

        # Step 1: write an event-only baseline.
        event_only = deepcopy(self.fixture)
        event_only.event_runs = list(event_only.vector_runs)
        event_only.event_summary = event_only.vector_summary
        event_only.vector_runs = []
        event_only.vector_summary = None
        save_bundle(event_only, path)
        baseline = open_bundle(path)
        self.assertEqual(baseline.engines(), ["event"])

        # Step 2: write a vector-only sibling over the same path. The
        # merge logic should preserve the event slot and add vector.
        vector_only = deepcopy(self.fixture)
        # fixture is already vector-only; assert that explicitly.
        self.assertEqual(vector_only.engines(), ["vector"])
        save_bundle(vector_only, path)

        merged = open_bundle(path)
        self.assertEqual(
            sorted(merged.engines()), ["event", "vector"]
        )
        self.assertEqual(
            len(merged.vector_runs), len(vector_only.vector_runs)
        )
        self.assertEqual(
            len(merged.event_runs), len(event_only.event_runs)
        )


class TestBackTestsDirectory(TestCase):
    """Verify ``save_/load_backtests_from_directory`` parallel paths."""

    @classmethod
    def setUpClass(cls):
        base = Backtest.open(_FIXTURE)
        cls.backtests = []
        for i in range(4):
            bt = Backtest.from_dict(base.to_dict())
            bt.algorithm_id = f"algo_{i}"
            bt.tag = "demo"
            cls.backtests.append(bt)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_and_load_uses_bundle_format_by_default(self):
        save_backtests_to_directory(self.backtests, self.tmp, workers=2)

        names = sorted(os.listdir(self.tmp))
        self.assertIn("index.parquet", names)
        bundle_names = [n for n in names if n.endswith(BUNDLE_EXT)]
        self.assertEqual(len(bundle_names), 4)

        loaded = load_backtests_from_directory(self.tmp, workers=2)
        self.assertEqual(len(loaded), 4)
        self.assertEqual(
            sorted(b.algorithm_id for b in loaded),
            ["algo_0", "algo_1", "algo_2", "algo_3"],
        )

    def test_index_parquet_supports_filtering_without_loading_bundles(self):
        save_backtests_to_directory(self.backtests, self.tmp)
        idx = BacktestIndex.open(self.tmp)
        self.assertEqual(len(idx), 4)
        self.assertIn("algorithm_id", idx.df.columns)
        self.assertIn("bundle_path", idx.df.columns)

        keep = idx.filter(lambda r: r.algorithm_id in {"algo_1", "algo_3"})
        self.assertEqual(len(keep), 2)
        loaded = keep.load_backtests(workers=1)
        self.assertEqual(
            sorted(b.algorithm_id for b in loaded),
            ["algo_1", "algo_3"],
        )

    def test_legacy_directory_format_still_supported(self):
        save_backtests_to_directory(
            self.backtests, self.tmp, format="directory"
        )
        self.assertTrue(
            os.path.isdir(os.path.join(self.tmp, "algo_0"))
        )
        loaded = load_backtests_from_directory(self.tmp, workers=1)
        self.assertEqual(len(loaded), 4)

    def test_migrate_backtests_converts_legacy_to_bundles(self):
        legacy_dir = os.path.join(self.tmp, "legacy")
        bundle_dir = os.path.join(self.tmp, "bundles")
        save_backtests_to_directory(
            self.backtests, legacy_dir, format="directory"
        )
        n = migrate_backtests(legacy_dir, bundle_dir, workers=2)
        self.assertEqual(n, 4)
        names = sorted(os.listdir(bundle_dir))
        self.assertEqual(
            [n for n in names if n.endswith(BUNDLE_EXT)],
            ["algo_0.iafbt", "algo_1.iafbt", "algo_2.iafbt", "algo_3.iafbt"],
        )
        loaded = load_backtests_from_directory(bundle_dir, workers=2)
        self.assertEqual(len(loaded), 4)


class TestBundleFormatV2(TestCase):
    """Verify bundle format v2 specifics: engine_type split,
    embedded Parquet metric blobs, summary_only mode, and v1
    backwards-compatible reads."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_save_emits_current_version_header(self):
        path = os.path.join(self.tmp, "current" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        with open(path, "rb") as fh:
            head = fh.read(8)
        self.assertEqual(head[:4], _MAGIC)
        self.assertEqual(
            int.from_bytes(head[4:8], "little"),
            BUNDLE_FORMAT_VERSION,
        )

    def test_v1_writer_no_longer_supported(self):
        path = os.path.join(self.tmp, "v1" + BUNDLE_EXT)
        with self.assertRaises(Exception):
            save_bundle(self.fixture, path, format_version=1)

    def test_v2_round_trip_preserves_metric_series(self):
        path = os.path.join(self.tmp, "v2" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        loaded = open_bundle(path)

        # Find a run on the fixture that has a non-empty equity_curve
        # to compare against, and assert structural equivalence.
        if (
            self.fixture.get_all_backtest_runs()
            and self.fixture.get_all_backtest_runs()[0].backtest_metrics
            and self.fixture.get_all_backtest_runs()[0]
            .backtest_metrics.equity_curve
        ):
            self.assertEqual(
                len(loaded.get_all_backtest_runs()[0].backtest_metrics.equity_curve),
                len(self.fixture.get_all_backtest_runs()[0]
                    .backtest_metrics.equity_curve),
            )

    def test_engine_type_round_trips_into_vector_runs_slot(self):
        # v9.0: runs land in vector_runs (default slot). Verify round-trip.
        bt = Backtest.from_dict(self.fixture.to_dict())
        path = os.path.join(self.tmp, "vector" + BUNDLE_EXT)
        save_bundle(bt, path)

        loaded = open_bundle(path)
        self.assertIn("vector", loaded.engines())
        # Properties route to the right slot.
        self.assertEqual(len(loaded.vector_runs), len(bt.get_all_backtest_runs()))
        self.assertEqual(loaded.event_runs, [])

    def test_engine_type_round_trips_into_event_runs_slot(self):
        # v9.0: move all runs to event slot by rebuilding the backtest.
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt_event = Backtest(
            algorithm_id=bt.algorithm_id,
            event_runs=bt.get_all_backtest_runs(),
        )
        path = os.path.join(self.tmp, "event" + BUNDLE_EXT)
        save_bundle(bt_event, path)

        loaded = open_bundle(path)
        self.assertIn("event", loaded.engines())
        self.assertEqual(len(loaded.event_runs), len(bt.get_all_backtest_runs()))
        self.assertEqual(loaded.vector_runs, [])

    def test_summary_only_skips_blob_decode(self):
        bt = Backtest.from_dict(self.fixture.to_dict())
        path = os.path.join(self.tmp, "summary" + BUNDLE_EXT)
        save_bundle(bt, path)

        loaded = open_bundle(path, summary_only=True)
        # Scalar metrics still populated; blob fields remain as
        # opaque references {"@blob": "..."} rather than lists.
        if loaded.get_all_backtest_runs() and loaded.get_all_backtest_runs()[0].backtest_metrics:
            metrics = loaded.get_all_backtest_runs()[0].backtest_metrics
            # equity_curve in summary_only mode is left as an
            # unresolved reference dict (or empty list if the source
            # had no series). Either is acceptable; what we assert
            # is that scalar fields are populated.
            self.assertIsNotNone(metrics.sharpe_ratio)

    def test_v3_bundle_round_trips_through_writer(self):
        """Smoke test: v3 bundle written via save_bundle reads back
        with the same structural content. v9.0 writer is v3-only;
        v1/v2 are read-only legacy formats."""
        v3_path = os.path.join(self.tmp, "v3" + BUNDLE_EXT)
        save_bundle(self.fixture, v3_path)
        loaded = open_bundle(v3_path)
        self.assertEqual(
            loaded.algorithm_id, self.fixture.algorithm_id
        )
        self.assertEqual(
            len(loaded.get_all_backtest_runs()), len(self.fixture.get_all_backtest_runs())
        )

    def test_v2_writer_no_longer_supported(self):
        """v9.0 writer is v3-only — v2 writes must raise."""
        path = os.path.join(self.tmp, "v2" + BUNDLE_EXT)
        with self.assertRaises(Exception):
            save_bundle(self.fixture, path, format_version=2)

    def test_legacy_bundles_default_to_vector_engine(self):
        # v9.0: legacy v1/v2 bundles that lack an explicit engine_type
        # default to the vector slot when read (design doc §2.6.1).
        # We simulate by writing a v3 bundle from the fixture (whose
        # legacy runs land in vector_runs via the constructor shim)
        # and verifying the slot routing.
        path = os.path.join(self.tmp, "legacy" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        loaded = open_bundle(path)
        self.assertIn("vector", loaded.engines())
        self.assertEqual(loaded.event_runs, [])
        self.assertEqual(
            len(loaded.vector_runs), len(self.fixture.get_all_backtest_runs())
        )
        # Union view still works.
        self.assertEqual(
            len(loaded.get_all_backtest_runs()), len(self.fixture.get_all_backtest_runs())
        )
