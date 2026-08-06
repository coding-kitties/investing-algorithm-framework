"""Phase 3a tests for the Study / EngineSlot domain model and the
new multi-study API on :class:`Backtest`.

These tests cover the *additive* derivation of ``Backtest.studies``
from existing top-level fields (``study_name`` / ``universes`` /
``vector_runs`` / ``vector_summaries_by_universe`` / etc.) and the
new public API: :meth:`Backtest.list_studies`,
:meth:`Backtest.get_study`, :meth:`Backtest.add_study`, and the
``study=`` kwarg on :meth:`Backtest.get_runs` /
:meth:`Backtest.get_summary`.

See ``docs/design/multi-study-bundle.md`` §4.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestDateRange,
    BacktestMetrics,
    BacktestRun,
    BacktestSummaryMetrics,
    EngineSlot,
    Study,
    StudySampleType,
    Universe,
)
from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)


def _make_run(
    *,
    start: datetime,
    end: datetime,
    name: str,
    universe_key: str | None = None,
    sharpe: float = 1.0,
) -> BacktestRun:
    window = BacktestWindow(
        train_range=BacktestDateRange(
            start_date=start,
            end_date=end,
            name=name,
        )
    )
    metrics = BacktestMetrics(
        backtest_window=window,
        sharpe_ratio=sharpe,
    )
    metadata: dict = {}
    if universe_key is not None:
        metadata["universe_key"] = universe_key
    return BacktestRun(
        backtest_metrics=metrics,
        backtest_window=window,
        initial_unallocated=1000.0,
        portfolio_snapshots=[],
        orders=[],
        positions=[],
        trades=[],
        metadata=metadata,
    )


def _summary(sharpe: float) -> BacktestSummaryMetrics:
    return BacktestSummaryMetrics(
        sharpe_ratio=sharpe,
    )


class StudyDataclassTests(unittest.TestCase):
    """Unit tests for the new :class:`Study` and :class:`EngineSlot`."""

    def test_engineslot_is_empty(self):
        slot = EngineSlot()
        self.assertTrue(slot.is_empty())

        slot.summary = _summary(1.0)
        self.assertFalse(slot.is_empty())

    def test_study_get_engine_creates_slot(self):
        s = Study(name="default")
        slot = s.get_engine("vector")
        self.assertIsInstance(slot, EngineSlot)
        self.assertIs(s.engine_results["vector"], slot)

    def test_study_sample_type_enum_serializes_as_string(self):
        study = Study(sample_type=StudySampleType.EXPLORATORY)

        self.assertEqual(str(StudySampleType.EXPLORATORY), "exploratory")
        self.assertEqual(study.to_dict()["sample_type"], "exploratory")

    def test_study_populated_engines_canonical_order(self):
        s = Study(name="default")
        s.engine_results["event"] = EngineSlot(summary=_summary(1.0))
        s.engine_results["vector"] = EngineSlot(summary=_summary(2.0))
        # vector first regardless of insertion order
        self.assertEqual(s.populated_engines(), ["vector", "event"])

    def test_study_repr_shows_empty_and_missing_structure(self):
        representation = repr(Study(name="empty"))

        self.assertIn("description=None", representation)
        self.assertIn("universe=None", representation)
        self.assertIn("backtest_windows=[]", representation)
        self.assertIn("engines=[]", representation)
        self.assertIn("'vector': <missing>", representation)
        self.assertIn("'event': <missing>", representation)
        self.assertIn("metadata={}", representation)
        self.assertIn("ohlcv_keys=[]", representation)

    def test_study_repr_summarizes_populated_engine_slot(self):
        study = Study(
            name="populated",
            engine_results={
                "vector": EngineSlot(summary=_summary(1.5)),
            },
        )

        representation = repr(study)

        self.assertIn("'vector': EngineSlot(", representation)
        self.assertIn("state='populated'", representation)
        self.assertIn("runs=0", representation)
        self.assertIn("summary='present'", representation)
        self.assertIn("monte_carlo_tests=0", representation)

    def test_study_to_dict_round_trip(self):
        u = Universe(key="majors", symbols=["BTC", "ETH"])
        run = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
            universe_key="majors",
        )
        s = Study(
            name="ema_cross",
            description="top quartile",
            universe=u,
            engine_results={"vector": EngineSlot(
                runs=[run],
                summary=_summary(1.5),
                summaries_by_universe={"majors": _summary(1.5)},
            )},
        )
        d = s.to_dict()
        rebuilt = Study.from_dict(d)
        self.assertEqual(rebuilt.name, "ema_cross")
        self.assertEqual(rebuilt.description, "top quartile")
        self.assertEqual(rebuilt.universe.key, "majors")
        self.assertEqual(len(rebuilt.engine_results["vector"].runs), 1)
        self.assertEqual(
            rebuilt.engine_results["vector"].summary.sharpe_ratio, 1.5,
        )
        self.assertEqual(
            rebuilt.engine_results["vector"]
            .summaries_by_universe["majors"].sharpe_ratio,
            1.5,
        )

    def test_study_from_dict_back_compat_universes_list(self):
        # Older serialisations stored universes as a list under "universes";
        # ``from_dict`` should accept it and take the first entry.
        legacy = {
            "name": "default",
            "description": None,
            "universes": [Universe(key="majors").to_dict()],
            "windows": [],
            "metadata": {},
            "engines": {},
        }
        rebuilt = Study.from_dict(legacy)
        self.assertIsNotNone(rebuilt.universe)
        self.assertEqual(rebuilt.universe.key, "majors")


class BacktestStudiesViewSingleStudyTests(unittest.TestCase):
    """``Backtest.studies`` derivation for the single-study case."""

    def setUp(self):
        self.run = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
        )

    def test_no_universes_no_study_name_yields_default(self):
        bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run],
            vector_summary=_summary(1.0),
        )
        names = bt.list_studies()
        self.assertEqual(names, ["default"])
        st = bt.get_study("default")
        self.assertIsNotNone(st)
        self.assertEqual(len(st.get_runs("vector")), 1)
        self.assertEqual(st.get_summary("vector").sharpe_ratio, 1.0)

    def test_no_universes_with_study_name(self):
        bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run],
            vector_summary=_summary(1.0),
            study_name="in_sample",
            study_description="hello",
        )
        self.assertEqual(bt.list_studies(), ["in_sample"])
        st = bt.get_study("in_sample")
        self.assertEqual(st.description, "hello")

    def test_get_summary_with_study_kwarg_default_study(self):
        bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run],
            vector_summary=_summary(1.0),
        )
        # Explicit study= returns the same as the default rule.
        self.assertEqual(
            bt.get_summary("vector", study="default").sharpe_ratio,
            1.0,
        )

    def test_get_summary_unknown_study_raises(self):
        bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run],
            vector_summary=_summary(1.0),
        )
        with self.assertRaises(OperationalException):
            bt.get_summary("vector", study="nope")

    def test_get_runs_with_study_kwarg(self):
        bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run],
            vector_summary=_summary(1.0),
        )
        runs = bt.get_runs("vector", study="default")
        self.assertEqual(len(runs), 1)


class BacktestStudiesViewMultiUniverseTests(unittest.TestCase):
    """``Backtest.studies`` derivation for multi-universe v4 bundles.

    Under Model C the bundle exposes **one** study slot whose
    ``universes`` registry lists every Universe; per-regime metrics
    live in ``EngineSlot.summaries_by_universe``.
    """

    def setUp(self):
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        alts = Universe(key="alts", symbols=["SOL", "AVAX"])
        self.majors = majors
        self.alts = alts
        self.run_majors = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
            universe_key="majors",
            sharpe=1.0,
        )
        self.run_alts = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
            universe_key="alts",
            sharpe=2.0,
        )
        self.bt = Backtest(
            algorithm_id="algo-1",
            vector_runs=[self.run_majors, self.run_alts],
            vector_summary=_summary(1.5),  # pooled
            universes=[majors, alts],
            vector_summaries_by_universe={
                "majors": _summary(1.0),
                "alts": _summary(2.0),
            },
            study_name="ema_cross",
        )

    def test_one_study_single_universe(self):
        # Each study holds exactly one universe; the Backtest catalogue
        # holds the full list when multiple universes are involved.
        self.assertEqual(self.bt.list_studies(), ["ema_cross"])
        st = self.bt.get_study("ema_cross")
        # Study.universe is the first / primary universe for this study.
        self.assertEqual(st.universe.key, "majors")
        # bt.universes (the catalogue) lists all universes.
        self.assertEqual(
            sorted(u.key for u in self.bt.universes), ["alts", "majors"],
        )

    def test_runs_carry_universe_key(self):
        st = self.bt.get_study("ema_cross")
        runs = st.get_runs("vector")
        self.assertEqual(len(runs), 2)
        keys = sorted((r.metadata or {}).get("universe_key") for r in runs)
        self.assertEqual(keys, ["alts", "majors"])

    def test_summaries_by_universe_in_engine_slot(self):
        st = self.bt.get_study("ema_cross")
        sbu = st.engine_results["vector"].summaries_by_universe
        self.assertEqual(sbu["majors"].sharpe_ratio, 1.0)
        self.assertEqual(sbu["alts"].sharpe_ratio, 2.0)

    def test_pooled_summary_on_engine_slot(self):
        st = self.bt.get_study("ema_cross")
        # Pooled summary covers both regimes.
        self.assertEqual(
            st.engine_results["vector"].summary.sharpe_ratio, 1.5,
        )

    def test_legacy_get_summary_returns_pooled(self):
        # Phase 3a keeps legacy semantics: study=None returns the
        # pooled top-level summary even when multiple universes
        # exist. Phase 3b will tighten this to the strict §4.3 rule.
        self.assertEqual(
            self.bt.get_summary("vector").sharpe_ratio, 1.5,
        )


class BacktestAddStudyTests(unittest.TestCase):
    """:meth:`Backtest.add_study` write-through behaviour."""

    def test_add_study_no_universes_sets_default(self):
        bt = Backtest(algorithm_id="algo-1")
        run = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
        )
        st = Study(
            name="oos",
            description="time-OOS",
            engine_results={"vector": EngineSlot(runs=[run])},
        )
        bt.add_study(st)
        self.assertEqual(bt.get_study().name, "oos")
        self.assertEqual(len(bt.vector_runs), 1)
        self.assertEqual(bt.list_studies(), ["oos"])

    def test_add_study_duplicate_name_raises(self):
        bt = Backtest(
            algorithm_id="algo-1",
            study_name="oos",
            vector_runs=[_make_run(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 2, 1, tzinfo=timezone.utc),
                name="2024-01",
            )],
        )
        with self.assertRaises(OperationalException):
            bt.add_study(Study(name="oos"))

    def test_add_study_extends_multi_universe_bundle(self):
        """Phase 3b: ``add_study`` adds a *separate* study slot when
        called against an already-populated bundle. The legacy
        "merge new universe into existing study" behaviour from
        Phase 3a was dropped because it conflated use case 3 (OOS,
        new study) with use case 5 (same study, new engine slot)."""
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        alts = Universe(key="alts", symbols=["SOL", "AVAX"])
        bt = Backtest(
            algorithm_id="algo-1",
            universes=[majors],
            vector_runs=[_make_run(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 2, 1, tzinfo=timezone.utc),
                name="2024-01",
                universe_key="majors",
            )],
            vector_summaries_by_universe={"majors": _summary(1.0)},
            study_name="in_sample",
        )
        new_run = _make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 2, 1, tzinfo=timezone.utc),
            name="2024-01",
        )
        new_study = Study(
            name="oos_alts",
            universe=alts,
            engine_results={"vector": EngineSlot(
                runs=[new_run], summary=_summary(2.0),
            )},
        )
        bt.add_study(new_study)
        # Phase 3b: the original study is unchanged, the new study
        # is a discrete slot in studies.
        self.assertEqual(
            sorted(bt.list_studies()), ["in_sample", "oos_alts"],
        )
        self.assertEqual([u.key for u in bt.universes], ["majors"])
        self.assertEqual(len(bt.vector_runs), 1)
        # The new study lives in studies verbatim.
        self.assertIn("oos_alts", bt.studies)
        oos_alts = bt.studies["oos_alts"]
        self.assertEqual(oos_alts.universe.key, "alts")
        self.assertEqual(
            oos_alts.get_summary("vector").sharpe_ratio, 2.0,
        )

    def test_add_universe_less_study_to_multi_universe_raises(self):
        """Phase 3b: adding a universe-less study to a populated
        bundle no longer raises — it just lands in ``studies``
        as a separate slot. The Phase 3a guard against this is
        obsolete because studies are now discrete on disk.
        """
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        bt = Backtest(
            algorithm_id="algo-1",
            universes=[majors],
            vector_runs=[_make_run(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 2, 1, tzinfo=timezone.utc),
                name="2024-01",
                universe_key="majors",
            )],
        )
        bt.add_study(Study(name="event_default"))
        self.assertIn("event_default", bt.studies)

    def test_add_study_rejects_non_study(self):
        bt = Backtest(algorithm_id="algo-1")
        with self.assertRaises(TypeError):
            bt.add_study("not a study")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
