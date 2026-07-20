"""Tests for ``iaf migrate-bundles --to v3 <dir>`` (v9.0 Stage 7)."""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from click.testing import CliRunner

from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange
from investing_algorithm_framework.cli.cli import migrate_bundles_cmd
from investing_algorithm_framework.domain import (
    Backtest, BacktestRun, BacktestMetrics, PortfolioSnapshot,
)
from investing_algorithm_framework.domain.backtesting.bundle import (
    BUNDLE_EXT, BUNDLE_FORMAT_VERSION, peek_bundle_format_version,
    save_bundle, _build_v3_envelope, _encode_payload,
)


def _make_backtest(algo_id: str = "alpha") -> Backtest:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, tzinfo=timezone.utc)
    snap = PortfolioSnapshot(
        created_at=start.strftime("%Y-%m-%d %H:%M:%S"),
        total_value=1000, trading_symbol="EUR", unallocated=1000,
    )
    metrics = BacktestMetrics(
        backtest_start_date=start, backtest_end_date=end,
        equity_curve=[(1000, start), (1200, end)],
        drawdown_series=[(0, start), (-0.05, end)],
        total_net_gain=200, total_net_gain_percentage=0.20,
    )
    run = BacktestRun(
        backtest_window=BacktestWindow(
            train_range=BacktestDateRange(
                start_date=start,
                end_date=end,
                name="window_0",
            )
        ),
        orders=[], trades=[], positions=[],
        portfolio_snapshots=[snap], trading_symbol="EUR",
        initial_unallocated=1000,
        created_at=datetime.now(tz=timezone.utc),
        backtest_metrics=metrics,
    )
    return Backtest(
        algorithm_id=algo_id, vector_runs=[run], risk_free_rate=0.0,
    )


def _write_v2_bundle(target: Path, bt: Backtest) -> None:
    """Hand-write a fake v2-shaped bundle so the upgrader has something
    to upgrade. We reuse the v3 envelope builder but stamp the header
    with version=2 so ``peek_bundle_format_version`` reports v2 and
    the upgrader picks it up.
    """
    doc = _build_v3_envelope(bt)
    blob = _encode_payload(doc, format_version=2)
    target.write_bytes(blob)


class TestMigrateBundlesCommand(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skips_bundles_already_at_target_version(self):
        bt = _make_backtest("already_v3")
        target = self.tmp / f"already_v3{BUNDLE_EXT}"
        save_bundle(bt, target)
        self.assertEqual(
            peek_bundle_format_version(target), BUNDLE_FORMAT_VERSION,
        )

        result = CliRunner().invoke(
            migrate_bundles_cmd, [str(self.tmp), "--to", "v3"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("No upgrades needed", result.output)

    def test_upgrades_v2_bundle_in_place(self):
        bt = _make_backtest("legacy_v2")
        target = self.tmp / f"legacy_v2{BUNDLE_EXT}"
        # Build a fake v2-stamped bundle.
        _write_v2_bundle(target, bt)
        self.assertEqual(peek_bundle_format_version(target), 2)

        result = CliRunner().invoke(
            migrate_bundles_cmd,
            [str(self.tmp), "--to", "v3", "--no-index"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Upgraded 1 item", result.output)
        self.assertEqual(
            peek_bundle_format_version(target), BUNDLE_FORMAT_VERSION,
        )

    def test_dry_run_lists_without_writing(self):
        bt = _make_backtest("legacy_v2")
        target = self.tmp / f"legacy_v2{BUNDLE_EXT}"
        _write_v2_bundle(target, bt)
        original_mtime = target.stat().st_mtime_ns

        result = CliRunner().invoke(
            migrate_bundles_cmd,
            [str(self.tmp), "--to", "v3", "--dry-run"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Would upgrade 1 item", result.output)
        # File untouched.
        self.assertEqual(target.stat().st_mtime_ns, original_mtime)
        self.assertEqual(peek_bundle_format_version(target), 2)

    def test_legacy_directory_is_converted_and_removed(self):
        bt = _make_backtest("legacy_dir")
        dir_target = self.tmp / "legacy_dir"
        bt.save(str(dir_target))
        # Sanity: this is a legacy directory layout, not a bundle.
        self.assertTrue(dir_target.is_dir())
        self.assertTrue((dir_target / "algorithm_id.json").is_file())

        result = CliRunner().invoke(
            migrate_bundles_cmd,
            [str(self.tmp), "--to", "v3", "--no-index"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        bundle_path = self.tmp / f"legacy_dir{BUNDLE_EXT}"
        self.assertTrue(bundle_path.is_file())
        self.assertEqual(
            peek_bundle_format_version(bundle_path), BUNDLE_FORMAT_VERSION,
        )
        # Source directory removed by default.
        self.assertFalse(dir_target.exists())

    def test_keep_source_preserves_legacy_directory(self):
        bt = _make_backtest("legacy_keep")
        dir_target = self.tmp / "legacy_keep"
        bt.save(str(dir_target))

        result = CliRunner().invoke(
            migrate_bundles_cmd,
            [str(self.tmp), "--to", "v3", "--no-index", "--keep-source"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertTrue(dir_target.is_dir())
        self.assertTrue(
            (self.tmp / f"legacy_keep{BUNDLE_EXT}").is_file()
        )
