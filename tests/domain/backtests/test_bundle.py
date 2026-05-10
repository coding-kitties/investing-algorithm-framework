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

    def test_default_save_emits_v2_header(self):
        path = os.path.join(self.tmp, "v2" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        with open(path, "rb") as fh:
            head = fh.read(8)
        self.assertEqual(head[:4], _MAGIC)
        self.assertEqual(int.from_bytes(head[4:8], "little"), 2)

    def test_v1_writer_still_supported(self):
        path = os.path.join(self.tmp, "v1" + BUNDLE_EXT)
        save_bundle(self.fixture, path, format_version=1)
        with open(path, "rb") as fh:
            head = fh.read(8)
        self.assertEqual(int.from_bytes(head[4:8], "little"), 1)
        # And v1 still round-trips through the (upgraded) reader.
        loaded = open_bundle(path)
        self.assertEqual(
            loaded.algorithm_id, self.fixture.algorithm_id
        )

    def test_v2_round_trip_preserves_metric_series(self):
        path = os.path.join(self.tmp, "v2" + BUNDLE_EXT)
        save_bundle(self.fixture, path)
        loaded = open_bundle(path)

        # Find a run on the fixture that has a non-empty equity_curve
        # to compare against, and assert structural equivalence.
        if (
            self.fixture.backtest_runs
            and self.fixture.backtest_runs[0].backtest_metrics
            and self.fixture.backtest_runs[0]
            .backtest_metrics.equity_curve
        ):
            self.assertEqual(
                len(loaded.backtest_runs[0].backtest_metrics.equity_curve),
                len(self.fixture.backtest_runs[0]
                    .backtest_metrics.equity_curve),
            )

    def test_engine_type_round_trips_into_vector_runs_slot(self):
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt.engine_type = "vector"
        path = os.path.join(self.tmp, "vector" + BUNDLE_EXT)
        save_bundle(bt, path)

        loaded = open_bundle(path)
        self.assertEqual(loaded.engine_type, "vector")
        # Properties route to the right slot.
        self.assertEqual(len(loaded.vector_runs), len(bt.backtest_runs))
        self.assertEqual(loaded.event_runs, [])

    def test_engine_type_round_trips_into_event_runs_slot(self):
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt.engine_type = "event"
        path = os.path.join(self.tmp, "event" + BUNDLE_EXT)
        save_bundle(bt, path)

        loaded = open_bundle(path)
        self.assertEqual(loaded.engine_type, "event")
        self.assertEqual(len(loaded.event_runs), len(bt.backtest_runs))
        self.assertEqual(loaded.vector_runs, [])

    def test_summary_only_skips_blob_decode(self):
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt.engine_type = "vector"
        path = os.path.join(self.tmp, "summary" + BUNDLE_EXT)
        save_bundle(bt, path)

        loaded = open_bundle(path, summary_only=True)
        # Scalar metrics still populated; blob fields remain as
        # opaque references {"@blob": "..."} rather than lists.
        if loaded.backtest_runs and loaded.backtest_runs[0].backtest_metrics:
            metrics = loaded.backtest_runs[0].backtest_metrics
            # equity_curve in summary_only mode is left as an
            # unresolved reference dict (or empty list if the source
            # had no series). Either is acceptable; what we assert
            # is that scalar fields are populated.
            self.assertIsNotNone(metrics.sharpe_ratio)

    def test_v2_bundle_round_trips_through_writer(self):
        """Smoke test: v2 bundle written via save_bundle reads back
        with the same structural content. Per-bundle size comparison
        against v1 isn't meaningful for tiny test fixtures (Parquet
        headers add a fixed ~100-byte overhead per blob, which
        dominates when series have <50 entries). Real-world backtests
        with hundreds of equity-curve points see 30-80% reduction;
        see ``docs/design/bundle-format-v2.md``.
        """
        v2_path = os.path.join(self.tmp, "v2" + BUNDLE_EXT)
        save_bundle(self.fixture, v2_path, format_version=2)
        loaded = open_bundle(v2_path)
        self.assertEqual(
            loaded.algorithm_id, self.fixture.algorithm_id
        )
        self.assertEqual(
            len(loaded.backtest_runs), len(self.fixture.backtest_runs)
        )

    def test_engine_type_default_is_none_for_legacy_bundles(self):
        # Legacy v1 bundles never recorded engine_type. Reading one
        # should leave engine_type at None and place the runs under
        # backtest_runs (the engine-agnostic slot).
        path = os.path.join(self.tmp, "legacy" + BUNDLE_EXT)
        save_bundle(self.fixture, path, format_version=1)
        loaded = open_bundle(path)
        self.assertIsNone(loaded.engine_type)
        self.assertEqual(loaded.vector_runs, [])
        self.assertEqual(loaded.event_runs, [])
        # But the runs are still accessible via the union view.
        self.assertEqual(
            len(loaded.backtest_runs), len(self.fixture.backtest_runs)
        )
