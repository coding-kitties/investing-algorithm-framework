"""Tests for ``iaf migrate-store`` (epic #540 phase 3d)."""
from __future__ import annotations

import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

import pandas as pd
from click.testing import CliRunner

from investing_algorithm_framework.cli.cli import migrate_store_cmd
from investing_algorithm_framework.cli.migrate_store_command import (
    migrate_store,
)
from investing_algorithm_framework.domain import Backtest
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
    LocalTieredStore,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


def _make_ohlcv(symbol: str, *, n: int = 4, base: float = 100.0) -> dict:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "Datetime": idx,
            "Open": [base + i for i in range(n)],
            "High": [base + i + 0.5 for i in range(n)],
            "Low": [base + i - 0.5 for i in range(n)],
            "Close": [base + i + 0.25 for i in range(n)],
            "Volume": [1000 + i for i in range(n)],
        }
    )
    return {f"{symbol}:1h": df}


class TestMigrateStore(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.src_dir = tempfile.mkdtemp()
        self.dst_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Programmatic API
    # ------------------------------------------------------------------
    def test_local_dir_to_local_tiered(self):
        src = LocalDirStore(self.src_dir)
        src.write(self.fixture, handle="a")
        src.write(self.fixture, handle="b")

        n = migrate_store(
            src_kind="local-dir", src_root=self.src_dir,
            dst_kind="local-tiered", dst_root=self.dst_dir,
        )
        self.assertEqual(n, 2)

        dst = LocalTieredStore(self.dst_dir)
        self.assertEqual(len(dst), 2)
        self.assertTrue(dst.exists("a"))
        self.assertTrue(dst.exists("b"))
        # Tier-1 was populated.
        self.assertTrue((Path(self.dst_dir) / "index.sqlite").is_file())

    def test_handles_subset(self):
        src = LocalDirStore(self.src_dir)
        src.write(self.fixture, handle="a")
        src.write(self.fixture, handle="b")
        src.write(self.fixture, handle="c")

        n = migrate_store(
            src_kind="local-dir", src_root=self.src_dir,
            dst_kind="local-tiered", dst_root=self.dst_dir,
            handles=["a", "c"],
        )
        self.assertEqual(n, 2)
        dst = LocalTieredStore(self.dst_dir)
        self.assertSetEqual(
            set(dst.iter_handles()), {"a", "c"},
        )

    def test_ohlcv_dedup_during_migration(self):
        # Source is a tiered store (preserves OHLCV); destination is
        # a fresh tiered store. After migration, identical OHLCV must
        # collapse to a single chunk on the destination too.
        src = LocalTieredStore(self.src_dir)
        bt1 = deepcopy(self.fixture)
        bt1.ohlcv = _make_ohlcv("BTC/EUR")
        bt2 = deepcopy(self.fixture)
        bt2.ohlcv = _make_ohlcv("BTC/EUR")
        src.write(bt1, handle="a")
        src.write(bt2, handle="b")
        # Sanity: src already deduped to one chunk.
        self.assertEqual(src.ohlcv_stats()["stored_blobs"], 1)

        n = migrate_store(
            src_kind="local-tiered", src_root=self.src_dir,
            dst_kind="local-tiered", dst_root=self.dst_dir,
        )
        self.assertEqual(n, 2)

        # Phase 3c invariant: identical OHLCV stored once even though
        # two bundles reference it.
        dst = LocalTieredStore(self.dst_dir)
        self.assertEqual(dst.ohlcv_stats()["stored_blobs"], 1)
        self.assertEqual(dst.ohlcv_stats()["referenced_blobs"], 1)

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            migrate_store(
                src_kind="local-dir", src_root=self.src_dir,
                dst_kind="bogus", dst_root=self.dst_dir,
            )

    # ------------------------------------------------------------------
    # CLI
    # ------------------------------------------------------------------
    def test_cli_round_trip(self):
        src = LocalDirStore(self.src_dir)
        src.write(self.fixture, handle="cli_a")
        src.write(self.fixture, handle="cli_b")

        runner = CliRunner()
        result = runner.invoke(
            migrate_store_cmd,
            [
                "--from", "local-dir", "--src", self.src_dir,
                "--to", "local-tiered", "--dst", self.dst_dir,
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Migrated 2 backtest(s)", result.output)

        dst = LocalTieredStore(self.dst_dir)
        self.assertEqual(len(dst), 2)

    def test_cli_handles_subset(self):
        src = LocalDirStore(self.src_dir)
        for h in ("h1", "h2", "h3"):
            src.write(self.fixture, handle=h)

        runner = CliRunner()
        result = runner.invoke(
            migrate_store_cmd,
            [
                "--from", "local-dir", "--src", self.src_dir,
                "--to", "local-tiered", "--dst", self.dst_dir,
                "--handles", "h1,h3",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Migrated 2 backtest(s)", result.output)
        dst = LocalTieredStore(self.dst_dir)
        self.assertSetEqual(set(dst.iter_handles()), {"h1", "h3"})

    def test_cli_rejects_unknown_kind(self):
        runner = CliRunner()
        result = runner.invoke(
            migrate_store_cmd,
            [
                "--from", "bogus", "--src", self.src_dir,
                "--to", "local-tiered", "--dst", self.dst_dir,
            ],
        )
        # Click choice validation rejects with non-zero exit.
        self.assertNotEqual(result.exit_code, 0)
