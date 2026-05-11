"""Integration tests for the ``iaf index`` CLI (epic #540 phase 2)."""
import os
import shutil
import tempfile
from unittest import TestCase

from click.testing import CliRunner

from investing_algorithm_framework.domain import Backtest, BUNDLE_EXT
from investing_algorithm_framework.domain.backtesting.bundle import (
    save_bundle,
)
from investing_algorithm_framework.cli.cli import index_cmd
from investing_algorithm_framework.cli.index_command import build_index
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestIndexCommand(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Drop a few bundles into the temp dir.
        for i in range(3):
            bt = Backtest.from_dict(self.fixture.to_dict())
            bt.algorithm_id = f"algo_{i}"
            bt.tag = "demo"
            save_bundle(
                bt, os.path.join(self.tmp, f"algo_{i}{BUNDLE_EXT}"),
            )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Builder API
    # ------------------------------------------------------------------
    def test_build_index_writes_one_row_per_bundle(self):
        out = build_index(self.tmp, show_progress=False)
        self.assertTrue(os.path.isfile(out))

        with SqliteBacktestIndex.open(out) as idx:
            self.assertEqual(len(idx), 3)
            algos = sorted(r.algorithm_id for r in idx.iter_rows())
            self.assertEqual(algos, ["algo_0", "algo_1", "algo_2"])

    def test_build_index_uses_relative_paths_by_default(self):
        out = build_index(self.tmp, show_progress=False)
        with SqliteBacktestIndex.open(out) as idx:
            for row in idx.iter_rows():
                self.assertFalse(
                    os.path.isabs(row.bundle_path),
                    f"expected relative path, got {row.bundle_path}",
                )

    def test_build_index_absolute_paths_when_requested(self):
        out = build_index(
            self.tmp, show_progress=False, relative_paths=False,
        )
        with SqliteBacktestIndex.open(out) as idx:
            for row in idx.iter_rows():
                self.assertTrue(os.path.isabs(row.bundle_path))

    # ------------------------------------------------------------------
    # Click CLI surface
    # ------------------------------------------------------------------
    def test_cli_invocation(self):
        runner = CliRunner()
        out = os.path.join(self.tmp, "custom.sqlite")
        result = runner.invoke(
            index_cmd,
            [self.tmp, "--output", out, "--no-progress"],
        )
        self.assertEqual(
            result.exit_code, 0,
            msg=f"stdout={result.output!r} exc={result.exception!r}",
        )
        self.assertTrue(os.path.isfile(out))
        with SqliteBacktestIndex.open(out) as idx:
            self.assertEqual(len(idx), 3)
