"""Coverage for the v5 ``anchor_algorithm_id`` lineage attribute.

``anchor_algorithm_id`` is an optional pointer back to a primary /
anchor backtest, set on sibling bundles produced by follow-up
studies (param-robustness perturbations, cooldown-stress runs,
etc.). It rides through:

* the :class:`Backtest` dataclass (round-trips via ``to_dict`` /
  ``from_dict``);
* :meth:`Backtest.index_rows` (every emitted row carries it);
* :class:`BacktestIndexRow` flat-dict round-trip;
* the SQLite Tier-1 index (own column + secondary index);
* :func:`list_index` / :func:`rank_index`
  ``anchor_algorithm_id=`` filter, supporting an explicit
  ``"<none>"`` sentinel for ``IS NULL``;
* :func:`combine_backtests` (preserved on output, conflict on
  mismatch).
"""
import os
import shutil
import tempfile
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.cli.index_command import (
    list_index, rank_index,
)
from investing_algorithm_framework.domain import (
    Backtest,
    BacktestRun,
    BacktestSummaryMetrics,
)
from investing_algorithm_framework.domain.backtesting.backtest_index_row \
    import BacktestIndexRow
from investing_algorithm_framework.domain.backtesting.combine_backtests \
    import combine_backtests
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)


def _make_run(*, trades: int = 2) -> BacktestRun:
    return BacktestRun(
        backtest_window=BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            )
        ),
        initial_unallocated=10_000.0,
        number_of_runs=1,
        number_of_days=30,
        number_of_orders=trades,
        number_of_trades=trades,
    )


def _make_summary(sharpe: float) -> BacktestSummaryMetrics:
    return BacktestSummaryMetrics(
        sharpe_ratio=sharpe,
        total_net_gain=sharpe * 100.0,
        total_net_gain_percentage=sharpe,
        number_of_trades=10,
    )


def _make_backtest(
    *,
    algorithm_id: str,
    anchor: str | None,
    sharpe: float,
    study_name: str | None = None,
) -> Backtest:
    return Backtest(
        algorithm_id=algorithm_id,
        anchor_algorithm_id=anchor,
        study_name=(
            study_name
            if study_name is not None
            else "param_robustness" if anchor else "in_sample"
        ),
        vector_runs=[_make_run()],
        vector_summary=_make_summary(sharpe),
    )


class TestBacktestAnchorRoundTrip(TestCase):

    def test_default_is_none(self):
        bt = Backtest(algorithm_id="anchor-only")
        self.assertIsNone(bt.anchor_algorithm_id)

    def test_to_dict_from_dict_round_trip(self):
        bt = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=1.2,
        )
        restored = Backtest.from_dict(bt.to_dict())
        self.assertEqual(restored.anchor_algorithm_id, "anchor-7")

    def test_legacy_dict_without_anchor_decodes_to_none(self):
        # Simulate a pre-v5 envelope payload that has no
        # ``anchor_algorithm_id`` key at all.
        payload = _make_backtest(
            algorithm_id="anchor-x",
            anchor=None,
            sharpe=0.9,
        ).to_dict()
        payload.pop("anchor_algorithm_id")
        restored = Backtest.from_dict(payload)
        self.assertIsNone(restored.anchor_algorithm_id)


class TestIndexRowsCarryAnchor(TestCase):

    def test_emitted_row_propagates_anchor(self):
        bt = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=1.2,
        )
        rows = bt.index_rows(bundle_path="child-1.iafbt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].anchor_algorithm_id, "anchor-7")

    def test_anchor_bundle_emits_none(self):
        bt = _make_backtest(
            algorithm_id="anchor-7",
            anchor=None,
            sharpe=2.0,
        )
        rows = bt.index_rows(bundle_path="anchor-7.iafbt")
        self.assertEqual(rows[0].anchor_algorithm_id, None)


class TestBacktestIndexRowFlatDict(TestCase):

    def test_to_flat_dict_includes_anchor(self):
        row = BacktestIndexRow(
            algorithm_id="child-1",
            anchor_algorithm_id="anchor-7",
            bundle_path="child-1.iafbt",
            engine_type="vector",
        )
        flat = row.to_flat_dict()
        self.assertEqual(flat["anchor_algorithm_id"], "anchor-7")

    def test_from_flat_dict_round_trip(self):
        row = BacktestIndexRow(
            algorithm_id="child-1",
            anchor_algorithm_id="anchor-7",
            bundle_path="child-1.iafbt",
            engine_type="vector",
        )
        restored = BacktestIndexRow.from_flat_dict(row.to_flat_dict())
        self.assertEqual(restored.anchor_algorithm_id, "anchor-7")


class TestSqliteIndexAnchorColumn(TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")
        # Two children of the same anchor + a sibling under a
        # different anchor + the anchor itself (NULL anchor).
        self.bundles = [
            _make_backtest(
                algorithm_id="anchor-A",
                anchor=None,
                sharpe=2.0,
            ),
            _make_backtest(
                algorithm_id="child-A1",
                anchor="anchor-A",
                sharpe=1.6,
            ),
            _make_backtest(
                algorithm_id="child-A2",
                anchor="anchor-A",
                sharpe=1.4,
            ),
            _make_backtest(
                algorithm_id="child-B1",
                anchor="anchor-B",
                sharpe=0.9,
            ),
        ]
        with SqliteBacktestIndex.create(self.index_path) as idx:
            for bt in self.bundles:
                idx.upsert_many(
                    bt.index_rows(bundle_path=f"{bt.algorithm_id}.iafbt"),
                )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_secondary_index_exists(self):
        with SqliteBacktestIndex.open(self.index_path) as idx:
            cur = idx._conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name=?",
                ("idx_backtest_index_anchor_algorithm_id",),
            )
            self.assertIsNotNone(cur.fetchone())

    def test_filter_by_explicit_anchor(self):
        rows = list_index(
            self.index_path,
            anchor_algorithm_id="anchor-A",
            columns=("algorithm_id", "anchor_algorithm_id",
                     "summary_sharpe_ratio"),
        )
        algos = sorted(r["algorithm_id"] for r in rows)
        self.assertEqual(algos, ["child-A1", "child-A2"])
        for r in rows:
            self.assertEqual(r["anchor_algorithm_id"], "anchor-A")

    def test_filter_for_anchor_bundles_via_none_sentinel(self):
        rows = list_index(
            self.index_path,
            anchor_algorithm_id="<none>",
            columns=("algorithm_id", "anchor_algorithm_id"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["algorithm_id"], "anchor-A")
        self.assertIsNone(rows[0]["anchor_algorithm_id"])

    def test_rank_index_within_anchor_neighbourhood(self):
        # Rank only ``anchor-A``'s neighbourhood by Sharpe — the
        # primary use case the field was added for.
        ranked = rank_index(
            self.index_path,
            by="sharpe_ratio",
            anchor_algorithm_id="anchor-A",
        )
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["algorithm_id"], "child-A1")
        self.assertEqual(ranked[1]["algorithm_id"], "child-A2")


class TestCombineBacktestsAnchor(TestCase):

    def test_combine_preserves_anchor(self):
        a = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=1.0,
        )
        b = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=2.0,
        )
        combined = combine_backtests([a, b])
        self.assertEqual(combined.anchor_algorithm_id, "anchor-7")

    def test_combine_tolerates_missing_anchor_on_one_side(self):
        # ``None`` ride-alongs from un-stamped inputs are folded
        # into whichever side carries the explicit pointer.
        a = _make_backtest(
            algorithm_id="child-1",
            anchor=None,
            sharpe=1.0,
            study_name="param_robustness",
        )
        b = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=2.0,
        )
        combined = combine_backtests([a, b])
        self.assertEqual(combined.anchor_algorithm_id, "anchor-7")

    def test_combine_rejects_mismatched_anchors(self):
        a = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-7",
            sharpe=1.0,
        )
        b = _make_backtest(
            algorithm_id="child-1",
            anchor="anchor-9",
            sharpe=2.0,
        )
        with self.assertRaises(ValueError):
            combine_backtests([a, b])
