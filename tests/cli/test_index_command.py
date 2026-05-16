"""Integration tests for the ``iaf index`` CLI (epic #540 phase 2)."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from click.testing import CliRunner

from investing_algorithm_framework.domain import Backtest, BUNDLE_EXT
from investing_algorithm_framework.domain.backtesting.bundle import (
    save_bundle,
)
from investing_algorithm_framework.cli.cli import (
    index_cmd, list_cmd, rank_cmd,
)
from investing_algorithm_framework.cli.index_command import (
    build_index, list_index, rank_index, format_table, prune_backtests,
)
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

    # ------------------------------------------------------------------
    # list / rank helpers
    # ------------------------------------------------------------------
    def _build_index_with_metrics(self):
        """Build an index where each bundle has a distinct sharpe."""
        # Re-save with sharpe ratios 0.5 / 1.5 / 1.0 for ranking tests.
        sharpes = [0.5, 1.5, 1.0]
        for i, s in enumerate(sharpes):
            bt = Backtest.from_dict(self.fixture.to_dict())
            bt.algorithm_id = f"algo_{i}"
            bt.tag = "demo"
            if bt.backtest_summary is not None:
                bt.backtest_summary.sharpe_ratio = s
            save_bundle(
                bt, os.path.join(self.tmp, f"algo_{i}{BUNDLE_EXT}"),
            )
        return build_index(self.tmp, show_progress=False)

    def test_list_index_returns_dicts_with_default_columns(self):
        out = self._build_index_with_metrics()
        rows = list_index(out)
        self.assertEqual(len(rows), 3)
        self.assertIn("algorithm_id", rows[0])
        self.assertIn("summary_sharpe_ratio", rows[0])

    def test_list_index_sorts_descending_by_metric(self):
        out = self._build_index_with_metrics()
        rows = list_index(out, sort_by="sharpe_ratio")
        sharpes = [r["summary_sharpe_ratio"] for r in rows]
        self.assertEqual(sharpes, sorted(sharpes, reverse=True))

    def test_list_index_accepts_summary_prefixed_metric(self):
        out = self._build_index_with_metrics()
        rows = list_index(out, sort_by="summary_sharpe_ratio", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["algorithm_id"], "algo_1")  # 1.5 highest

    def test_list_index_accepts_directory_argument(self):
        self._build_index_with_metrics()
        rows = list_index(self.tmp, sort_by="sharpe_ratio", limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["algorithm_id"], "algo_1")

    def test_list_index_where_filter(self):
        out = self._build_index_with_metrics()
        rows = list_index(
            out,
            where="summary_sharpe_ratio >= 1.0",
            sort_by="sharpe_ratio",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [r["algorithm_id"] for r in rows], ["algo_1", "algo_2"],
        )

    def test_rank_index_returns_top_n(self):
        out = self._build_index_with_metrics()
        rows = rank_index(out, by="sharpe_ratio", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["algorithm_id"], "algo_1")
        self.assertEqual(rows[1]["algorithm_id"], "algo_2")

    def test_format_table_renders_header_and_rows(self):
        out = self._build_index_with_metrics()
        rows = rank_index(out, by="sharpe_ratio", limit=2)
        text = format_table(rows)
        self.assertIn("algorithm_id", text)
        self.assertIn("algo_1", text)
        # First data line should be algo_1 (highest sharpe).
        body = text.splitlines()[2]
        self.assertTrue(body.startswith("algo_1"))

    def test_cli_list_invocation(self):
        out = self._build_index_with_metrics()
        runner = CliRunner()
        result = runner.invoke(
            list_cmd, [out, "--sort", "sharpe_ratio", "-n", "2"],
        )
        self.assertEqual(
            result.exit_code, 0,
            msg=f"stdout={result.output!r} exc={result.exception!r}",
        )
        self.assertIn("algo_1", result.output)
        self.assertIn("algorithm_id", result.output)

    def test_cli_list_json_output(self):
        out = self._build_index_with_metrics()
        runner = CliRunner()
        result = runner.invoke(
            list_cmd, [out, "--sort", "sharpe_ratio", "--json"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertEqual(len(payload), 3)
        self.assertEqual(payload[0]["algorithm_id"], "algo_1")

    def test_cli_rank_invocation(self):
        out = self._build_index_with_metrics()
        runner = CliRunner()
        result = runner.invoke(
            rank_cmd, [out, "--by", "sharpe_ratio", "-n", "1"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("algo_1", result.output)
        self.assertNotIn("algo_0", result.output)

    def test_cli_rank_requires_by_flag(self):
        out = self._build_index_with_metrics()
        runner = CliRunner()
        result = runner.invoke(rank_cmd, [out])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--by", result.output)

    def test_list_on_directory_without_index_raises(self):
        # No index built yet in self.tmp.
        with self.assertRaises(FileNotFoundError):
            list_index(self.tmp)

    # ------------------------------------------------------------------
    # Incremental indexing (epic #540 phase 2)
    # ------------------------------------------------------------------
    def test_incremental_index_skips_unchanged_bundles(self):
        # First build — all bundles ingested.
        out = build_index(self.tmp, show_progress=False)
        with SqliteBacktestIndex.open(out) as idx:
            first_rows = list(idx.iter_rows())
        self.assertEqual(len(first_rows), 3)

        # Second build over an untouched directory — should skip
        # every bundle (we observe this via logging counters, but
        # the row count must stay stable and equal to 3).
        out2 = build_index(self.tmp, show_progress=False)
        self.assertEqual(out, out2)
        with SqliteBacktestIndex.open(out) as idx:
            second_rows = list(idx.iter_rows())
        self.assertEqual(len(second_rows), 3)

    def test_incremental_index_reingests_modified_bundle(self):
        out = build_index(self.tmp, show_progress=False)
        modified = os.path.join(self.tmp, f"algo_1{BUNDLE_EXT}")

        # Rewrite the bundle with a different algorithm_id + bump
        # mtime to force reingestion.
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt.algorithm_id = "algo_1_modified"
        bt.tag = "demo"
        save_bundle(bt, modified)
        # Ensure mtime actually changes on fast filesystems.
        future = os.stat(modified).st_mtime + 5
        os.utime(modified, (future, future))

        build_index(self.tmp, show_progress=False)
        with SqliteBacktestIndex.open(out) as idx:
            algos = sorted(r.algorithm_id for r in idx.iter_rows())
        self.assertEqual(
            algos, ["algo_0", "algo_1_modified", "algo_2"],
        )

    def test_full_rebuild_flag_disables_incremental(self):
        out = build_index(self.tmp, show_progress=False)
        # Simulate a stale entry by manually modifying the bundle on
        # disk without bumping mtime, then rebuild without incremental.
        modified = os.path.join(self.tmp, f"algo_2{BUNDLE_EXT}")
        original_stat = os.stat(modified)
        bt = Backtest.from_dict(self.fixture.to_dict())
        bt.algorithm_id = "algo_2_changed"
        bt.tag = "demo"
        save_bundle(bt, modified)
        # Restore the original mtime so incremental would skip it.
        os.utime(
            modified,
            (original_stat.st_atime, original_stat.st_mtime),
        )

        # Incremental would (incorrectly) skip; force a rebuild.
        build_index(self.tmp, show_progress=False, incremental=False)
        with SqliteBacktestIndex.open(out) as idx:
            algos = sorted(r.algorithm_id for r in idx.iter_rows())
        self.assertIn("algo_2_changed", algos)

    def test_scalar_summary_alias_matches_get_backtest_summary(self):
        self.assertIs(
            self.fixture.scalar_summary(),
            self.fixture.get_backtest_summary(),
        )

    # ------------------------------------------------------------------
    # prune_backtests
    # ------------------------------------------------------------------
    def test_prune_deletes_bundles_not_in_keep(self):
        self._build_index_with_metrics()
        top = rank_index(self.tmp, by="sharpe_ratio", limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["algorithm_id"], "algo_1")

        result = prune_backtests(self.tmp, keep=top)
        self.assertEqual(result["kept"], 1)
        self.assertEqual(result["pruned"], 2)
        self.assertIsNone(result["archive_dir"])

        # Only algo_1 remains on disk.
        remaining = list(
            p.name for p in sorted(
                Path(self.tmp).glob(f"*{BUNDLE_EXT}")
            )
        )
        self.assertEqual(remaining, [f"algo_1{BUNDLE_EXT}"])

    def test_prune_moves_to_archive_dir(self):
        self._build_index_with_metrics()
        top = rank_index(self.tmp, by="sharpe_ratio", limit=1)
        archive = os.path.join(self.tmp, "_archive")

        result = prune_backtests(
            self.tmp, keep=top, archive_dir=archive,
        )
        self.assertEqual(result["pruned"], 2)
        self.assertEqual(result["kept"], 1)

        # Archive dir should contain the two pruned bundles.
        archived = sorted(
            p.name for p in Path(archive).glob(f"*{BUNDLE_EXT}")
        )
        self.assertEqual(len(archived), 2)
        self.assertIn(f"algo_0{BUNDLE_EXT}", archived)
        self.assertIn(f"algo_2{BUNDLE_EXT}", archived)

        # Source still has the winner.
        remaining = list(
            p.name for p in Path(self.tmp).glob(f"*{BUNDLE_EXT}")
        )
        self.assertEqual(remaining, [f"algo_1{BUNDLE_EXT}"])

    def test_prune_dry_run_does_not_touch_files(self):
        self._build_index_with_metrics()
        top = rank_index(self.tmp, by="sharpe_ratio", limit=1)

        result = prune_backtests(self.tmp, keep=top, dry_run=True)
        self.assertEqual(result["pruned"], 2)
        self.assertEqual(result["kept"], 1)

        # All three bundles should still be on disk.
        remaining = sorted(
            p.name for p in Path(self.tmp).glob(f"*{BUNDLE_EXT}")
        )
        self.assertEqual(len(remaining), 3)

    def test_prune_refreshes_index(self):
        self._build_index_with_metrics()
        top = rank_index(self.tmp, by="sharpe_ratio", limit=1)

        prune_backtests(self.tmp, keep=top)

        # Index should now contain only the kept bundle.
        rows = list_index(self.tmp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["algorithm_id"], "algo_1")
