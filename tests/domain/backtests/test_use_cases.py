"""Phase 3b end-to-end use-case tests for the multi-study bundle format.

Covers the five canonical use cases enumerated in
``docs/design/backtest-bundle-format.md`` §"Use cases":

1. **In-sample sweep** — single study, single universe, multiple
   windows; round-trip preserves runs / summaries.
2. **In-sample extension** — same algorithm, two studies sharing the
   same universe (e.g. signal sweep + signal sweep with cooldown);
   both studies live side-by-side in one bundle.
3. **Out-of-sample evaluation** — two studies with *different*
   universes ("majors" in-sample, "alts" OOS); each study owns its
   own universe registry.
4. **Event engine as a separate study** — vector results in one
   study, event-driven results in a second study with a different
   name; engines are scoped per-study.
5. **Event engine on the same study** — single study with both
   ``vector`` and ``event`` engine slots populated; engines coexist
   in one study slot.

The shared invariant verified across all five tests: ``save_bundle``
followed by ``open_bundle`` (or :py:meth:`Backtest.open`) preserves
the entire studies map — names, descriptions, universes, runs and
summaries.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from unittest import TestCase
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestMetrics,
    BacktestRun,
    BacktestSummaryMetrics,
    BUNDLE_EXT,
    EngineSlot,
    Study,
    Universe,
)
from investing_algorithm_framework.domain.backtesting.bundle import (
    open_bundle,
    save_bundle,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(
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
    return BacktestSummaryMetrics(sharpe_ratio=sharpe)


class _BundleRoundTripBase(TestCase):
    """Shared scaffolding: temp dir + ``round_trip`` helper."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def round_trip(self, backtest: Backtest, name: str = "report") -> Backtest:
        path = os.path.join(self.tmp, name + BUNDLE_EXT)
        save_bundle(backtest, path)
        self.assertTrue(os.path.isfile(path))
        return open_bundle(path)


# ---------------------------------------------------------------------------
# Use case 1: in-sample sweep (single study, single universe)
# ---------------------------------------------------------------------------


class TestUseCase1InSample(_BundleRoundTripBase):
    """UC1: single study with one universe and multiple windows."""

    def _build(self) -> Backtest:
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        runs = [
            _run(
                start=datetime(2024, m, 1, tzinfo=timezone.utc),
                end=datetime(2024, m + 1, 1, tzinfo=timezone.utc),
                name=f"2024-{m:02d}",
                universe_key="majors",
                sharpe=1.0 + 0.1 * m,
            )
            for m in range(1, 4)
        ]
        return Backtest(
            algorithm_id="uc1-algo",
            study_name="in_sample",
            study_description="UC1 in-sample sweep",
            universes=[majors],
            vector_runs=runs,
            vector_summary=_summary(1.5),
        )

    def test_round_trip_preserves_single_study(self):
        original = self._build()
        loaded = self.round_trip(original, "uc1")

        self.assertEqual(loaded.algorithm_id, "uc1-algo")
        self.assertEqual(loaded.get_study().name, "in_sample")
        self.assertEqual(loaded.list_studies(), ["in_sample"])
        # Runs / summary preserved on legacy slot
        self.assertEqual(len(loaded.vector_runs), 3)
        self.assertEqual(len(loaded.event_runs), 0)
        self.assertAlmostEqual(loaded.vector_summary.sharpe_ratio, 1.5)
        self.assertEqual(
            [u.key for u in loaded.universes], ["majors"]
        )

    def test_studies_view_exposes_default(self):
        loaded = self.round_trip(self._build(), "uc1b")
        study = loaded.get_study("in_sample")
        self.assertIsInstance(study, Study)
        self.assertEqual(study.universe.key, "majors")
        self.assertEqual(len(study.engine_results["vector"].runs), 3)


# ---------------------------------------------------------------------------
# Use case 2: in-sample extension (two studies, shared universe)
# ---------------------------------------------------------------------------


class TestUseCase2InSampleExtension(_BundleRoundTripBase):
    """UC2: same algorithm, two studies sharing one universe."""

    def _build(self) -> Backtest:
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        bt = Backtest(
            algorithm_id="uc2-algo",
            study_name="in_sample_signal_sweep",
            universes=[majors],
            vector_runs=[
                _run(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 4, 1, tzinfo=timezone.utc),
                    name="Q1",
                    universe_key="majors",
                    sharpe=1.2,
                )
            ],
            vector_summary=_summary(1.2),
        )
        bt.add_study(
            Study(
                name="in_sample_signal_sweep_with_cooldown",
                description="Same window + cooldown filter",
                universe=majors,
                engine_results={
                    "vector": EngineSlot(
                        runs=[
                            _run(
                                start=datetime(
                                    2024, 1, 1, tzinfo=timezone.utc
                                ),
                                end=datetime(
                                    2024, 4, 1, tzinfo=timezone.utc
                                ),
                                name="Q1",
                                universe_key="majors",
                                sharpe=1.7,
                            )
                        ],
                        summary=_summary(1.7),
                    ),
                },
            )
        )
        return bt

    def test_round_trip_preserves_both_studies(self):
        loaded = self.round_trip(self._build(), "uc2")

        self.assertEqual(
            loaded.list_studies(),
            ["in_sample_signal_sweep", "in_sample_signal_sweep_with_cooldown"],
        )
        # Default slot still hosts the first study
        self.assertEqual(loaded.get_study().name, "in_sample_signal_sweep")
        self.assertEqual(len(loaded.vector_runs), 1)
        # Second study round-tripped via studies
        self.assertIn(
            "in_sample_signal_sweep_with_cooldown", loaded.studies
        )
        cooldown = loaded.studies["in_sample_signal_sweep_with_cooldown"]
        self.assertEqual(cooldown.universe.key, "majors")
        self.assertAlmostEqual(
            cooldown.engine_results["vector"].summary.sharpe_ratio, 1.7
        )


# ---------------------------------------------------------------------------
# Use case 3: out-of-sample evaluation (two studies, different universes)
# ---------------------------------------------------------------------------


class TestUseCase3OutOfSample(_BundleRoundTripBase):
    """UC3: in-sample on one universe, OOS on a different universe."""

    def _build(self) -> Backtest:
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        alts = Universe(key="alts", symbols=["SOL", "DOT"])

        bt = Backtest(
            algorithm_id="uc3-algo",
            study_name="in_sample",
            universes=[majors],
            vector_runs=[
                _run(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                    name="IS",
                    universe_key="majors",
                    sharpe=1.4,
                )
            ],
            vector_summary=_summary(1.4),
        )
        bt.add_study(
            Study(
                name="oos",
                description="Out-of-sample on alts",
                universe=alts,
                engine_results={
                    "vector": EngineSlot(
                        runs=[
                            _run(
                                start=datetime(
                                    2024, 6, 1, tzinfo=timezone.utc
                                ),
                                end=datetime(
                                    2024, 12, 1, tzinfo=timezone.utc
                                ),
                                name="OOS",
                                universe_key="alts",
                                sharpe=0.9,
                            )
                        ],
                        summary=_summary(0.9),
                    ),
                },
            )
        )
        return bt

    def test_each_study_owns_its_universe(self):
        loaded = self.round_trip(self._build(), "uc3")

        self.assertEqual(loaded.list_studies(), ["in_sample", "oos"])
        # Default study sees majors
        in_sample = loaded.get_study("in_sample")
        self.assertEqual(in_sample.universe.key, "majors")
        # OOS study sees alts only — universes are not merged
        oos = loaded.get_study("oos")
        self.assertEqual(oos.universe.key, "alts")
        # Backtest-level legacy ``universes`` still reflects the
        # default study only
        self.assertEqual([u.key for u in loaded.universes], ["majors"])


# ---------------------------------------------------------------------------
# Use case 4: event engine as a separate study
# ---------------------------------------------------------------------------


class TestUseCase4EventAsNewStudy(_BundleRoundTripBase):
    """UC4: vector run + event-driven run as two distinct studies."""

    def _build(self) -> Backtest:
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        bt = Backtest(
            algorithm_id="uc4-algo",
            study_name="vector_default",
            universes=[majors],
            vector_runs=[
                _run(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                    name="V",
                    universe_key="majors",
                    sharpe=1.3,
                )
            ],
            vector_summary=_summary(1.3),
        )
        bt.add_study(
            Study(
                name="event_replay",
                description="Event-driven replay of the same window",
                universe=majors,
                engine_results={
                    "event": EngineSlot(
                        runs=[
                            _run(
                                start=datetime(
                                    2024, 1, 1, tzinfo=timezone.utc
                                ),
                                end=datetime(
                                    2024, 6, 1, tzinfo=timezone.utc
                                ),
                                name="E",
                                universe_key="majors",
                                sharpe=1.1,
                            )
                        ],
                        summary=_summary(1.1),
                    ),
                },
            )
        )
        return bt

    def test_engines_are_scoped_per_study(self):
        loaded = self.round_trip(self._build(), "uc4")

        self.assertEqual(loaded.list_studies(), ["vector_default", "event_replay"])

        vector_study = loaded.get_study("vector_default")
        self.assertEqual(
            list(vector_study.populated_engines()), ["vector"]
        )

        event_study = loaded.get_study("event_replay")
        self.assertEqual(
            list(event_study.populated_engines()), ["event"]
        )
        self.assertAlmostEqual(
            event_study.engine_results["event"].summary.sharpe_ratio, 1.1
        )


# ---------------------------------------------------------------------------
# Use case 5: event engine on the same study (two engines, one study)
# ---------------------------------------------------------------------------


class TestUseCase5EventSameStudy(_BundleRoundTripBase):
    """UC5: single study with both vector and event engine slots."""

    def _build(self) -> Backtest:
        majors = Universe(key="majors", symbols=["BTC", "ETH"])
        return Backtest(
            algorithm_id="uc5-algo",
            study_name="cross_engine",
            study_description="Vector + event on the same study",
            universes=[majors],
            vector_runs=[
                _run(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                    name="V",
                    universe_key="majors",
                    sharpe=1.3,
                )
            ],
            vector_summary=_summary(1.3),
            event_runs=[
                _run(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                    name="E",
                    universe_key="majors",
                    sharpe=1.1,
                )
            ],
            event_summary=_summary(1.1),
        )

    def test_single_study_hosts_both_engines(self):
        loaded = self.round_trip(self._build(), "uc5")

        self.assertEqual(loaded.list_studies(), ["cross_engine"])

        study = loaded.get_study("cross_engine")
        self.assertEqual(
            list(study.populated_engines()), ["vector", "event"]
        )
        self.assertAlmostEqual(
            study.engine_results["vector"].summary.sharpe_ratio, 1.3
        )
        self.assertAlmostEqual(
            study.engine_results["event"].summary.sharpe_ratio, 1.1
        )
        # Legacy scalar slots remain populated for the default study
        self.assertEqual(len(loaded.vector_runs), 1)
        self.assertEqual(len(loaded.event_runs), 1)
