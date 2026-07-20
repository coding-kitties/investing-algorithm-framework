"""Study and EngineSlot dataclasses for the multi-study bundle model.

A :class:`Study` is the algorithm-centric unit of evidence: it owns a
strategy idea / signal, a set of date-range windows, exactly one
universe it was evaluated on, and per-engine slots that hold the runs
and roll-up summaries. Multiple studies can live inside a single
:class:`Backtest` envelope (one per signal/universe variant).

The per-run universe lives on each :class:`BacktestRun`; the
``Study.universe`` field names which universe the whole study targets.

This module is the in-memory domain model. The on-disk bundle format
(``v4`` envelope today, ``v5`` zip + parquet sub-files in Phase 3b)
serialises to/from this shape.

See ``docs/design/multi-study-bundle.md`` §4 for the binding contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .backtest_monte_carlo_test import BacktestMonteCarloTest
from .backtest_run import BacktestRun
from .backtest_summary_metrics import BacktestSummaryMetrics
from .backtest_date_range import BacktestDateRange
from .backtest_window import BacktestWindow
from .universe import Universe
from .combine_backtests import generate_backtest_summary_metrics
from .backtest_engine import BacktestEngine


@dataclass
class EngineSlot:
    """Per-engine container for runs and roll-up summaries.

    Attributes:
        runs: Walk-forward runs produced by one engine for the
            owning :class:`Study`. Each run carries its own
            :class:`Universe` (the regime axis lives on the run,
            not the study).
        summary: Cross-window scalar roll-up pooled across **all**
            runs in this slot, irrespective of universe. ``None``
            when the slot is empty or hasn't been computed yet.
        summaries_by_universe: Cached per-regime roll-up keyed by
            :pyattr:`Universe.key`. ``{}`` when the study has only
            one universe (``summary`` already covers that case) or
            when the cache hasn't been populated.
    """

    runs: List[BacktestRun] = field(default_factory=list)
    summary: Optional[BacktestSummaryMetrics] = None
    summaries_by_universe: Dict[str, BacktestSummaryMetrics] = field(
        default_factory=dict
    )

    def is_empty(self) -> bool:
        """Return True iff the slot carries no runs and no summary."""
        return (
            not self.runs
            and self.summary is None
            and not self.summaries_by_universe
        )


@dataclass
class Study:
    """One strategy idea / signal evaluated by an algorithm.

    A study identifies *what* is being tested (the signal, the
    parameter set, the variant). The *where* — i.e. which
    universe(s) it was evaluated on — lives on each
    :class:`BacktestRun`.

    Each :class:`Study` is tied to **exactly one** universe (the
    instrument set it traded). To compare results across different
    universes create one :class:`Study` per universe, all held by the
    same parent :class:`Backtest` envelope.

    vector_summary, event_summary, and summaries_by_universe are study-level
    aggregates across runs. Tier 1 is one-row-per-run by design.
    These have two options when tiered storage ships:

    1. Derive on demand — SELECT from the Tier 1 backtest_runs table and re-compute generate_backtest_summary_metrics over the filtered set. This is actually what get_metrics() already does in-memory.
    2. Separate table — a study_summaries table with one row per (study_name, engine), storing the pre-computed aggregate. Mirrors today's summary field.
    backtest_windows on the study is also redundant in tiered storage — each run row already carries start_date/end_date/date_range_name, so the window catalogue can be reconstructed with SELECT DISTINCT. It stays in the Study for the .iafbt export path and for in-memory filtering without a SQL query.

    Attributes:
        name: Stable identifier for this study within its parent
            :class:`Backtest`. Conventionally lower_snake_case
            (``"ema_cross"``, ``"momentum_v2"``). The runner
            defaults to ``"default"`` when no name is supplied.
        description: Optional free-form description.
        windows: Date-range windows the study ran on.
        universe: The single :class:`Universe` this study was
            evaluated on. ``None`` for universe-agnostic studies.
        engines: Per-engine slots keyed by ``"vector"`` /
            ``"event"``. Missing keys mean that engine wasn't run
            for this study.
        metadata: Free-form per-study metadata (e.g. provenance
            tags, parameter fingerprints, fold IDs).
    """

    name: str = "default"
    description: Optional[str] = None
    backtest_windows: List[BacktestWindow] = field(default_factory=list)
    universe: Optional[Universe] = None
    # Client facing only, will not be persisted in the bundle.
    # Use engine_results for persisted data.
    engines: List[BacktestEngine] = field(default_factory=list)
    engine_results: Dict[str, EngineSlot] = field(default_factory=dict)
    monte_carlo_tests: List[BacktestMonteCarloTest] = field(
        default_factory=list
    )
    metadata: Dict[str, str] = field(default_factory=dict)
    # OHLCV price payload for this study. Keys are "<symbol>@<timeframe>"
    # (e.g. "BTC/EUR@1h"), values are pandas DataFrames. Populated when
    # the bundle was saved with ``include_ohlcv=True``. Not included in
    # JSON serialisation (handled at the bundle layer as Parquet blobs).
    ohlcv: Dict[str, object] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Backward-compat universe list view
    # ------------------------------------------------------------------

    @property
    def universes(self) -> List[Universe]:
        """Read-only backward-compat view; returns ``[self.universe]``
        when a universe is set, otherwise ``[]``."""
        return [self.universe] if self.universe is not None else []

    @property
    def engine(self) -> Optional["BacktestEngine"]:
        """Return the first engine in ``self.engines``, or ``None`` if
        no engine has been configured."""
        return self.engines[0] if self.engines else None

    # ------------------------------------------------------------------
    # Engine accessors

    def get_engine(self, engine: str) -> EngineSlot:
        """Return the :class:`EngineSlot` for ``engine``, creating an
        empty slot if it doesn't yet exist.

        Args:
            engine: ``"vector"`` or ``"event"``.
        """
        if engine not in self.engine_results:
            self.engine_results[engine] = EngineSlot()
        return self.engine_results[engine]

    def get_summary(self, engine: str) -> Optional[BacktestSummaryMetrics]:
        """Return the pooled summary for ``engine`` (``None`` if no slot)."""
        slot = self.engine_results.get(engine)
        return slot.summary if slot is not None else None

    def get_metrics(
        self,
        engine: str,
        backtest_window: BacktestWindow = None,
        backtest_windows: List[BacktestWindow] = None,
    ) -> Optional[BacktestSummaryMetrics]:
        """Return roll-up metrics for ``engine``, optionally scoped to
        specific window(s).

        When no window filter is provided, returns the pre-computed pooled
        summary from the engine slot (same as :meth:`get_summary`).

        When a window filter is provided, derives a fresh
        :class:`BacktestSummaryMetrics` from only the runs that fall within
        the specified window(s).  Returns ``None`` when no matching runs are
        found.

        Args:
            engine: ``"vector"`` or ``"event"``.
            backtest_window: Limit to runs within this single window.
                Mutually exclusive with ``backtest_windows``.
            backtest_windows: Limit to runs within any of these windows.
                Mutually exclusive with ``backtest_window``.
        """
        if backtest_window is None and backtest_windows is None:
            return self.get_summary(engine)

        filtered = self.get_runs(
            engine=engine,
            backtest_window=backtest_window,
            backtest_windows=backtest_windows,
        )
        if not filtered:
            return None
        per_run = [
            r.backtest_metrics for r in filtered
            if r.backtest_metrics is not None
        ]
        if not per_run:
            return None
        return generate_backtest_summary_metrics(per_run)

    def get_runs(
        self,
        engine: str = None,
        backtest_window: BacktestWindow = None,
        backtest_windows: List[BacktestWindow] = None,
    ) -> List[BacktestRun]:
        """Return runs for ``engine``, optionally filtered by window(s).

        A run matches a :class:`BacktestWindow` when its
        ``backtest_start_date`` / ``backtest_end_date`` equal the
        window's ``test_range`` dates (if the window has a test range)
        or the window's ``train_range`` dates (for train-only windows).

        Args:
            engine: ``"vector"`` or ``"event"``. Required.
            backtest_window: Filter to runs that fall within this single
                window. Mutually exclusive with ``backtest_windows``.
            backtest_windows: Filter to runs that fall within any of
                these windows. Mutually exclusive with
                ``backtest_window``.

        Returns:
            Filtered (or unfiltered) list of :class:`BacktestRun`.
        """
        slot = self.engine_results.get(engine)
        if slot is None:
            return []

        runs = list(slot.runs)

        # Build the effective window list to filter against.
        windows_to_match: Optional[List[BacktestWindow]] = None
        if backtest_window is not None and backtest_windows is not None:
            raise ValueError(
                "Provide either backtest_window or backtest_windows, not both."
            )
        if backtest_window is not None:
            windows_to_match = [backtest_window]
        elif backtest_windows is not None:
            windows_to_match = list(backtest_windows)

        if windows_to_match is None:
            return runs

        def _run_matches(run: BacktestRun, window: BacktestWindow) -> bool:
            date_range = (
                window.test_range
                if window.test_range is not None
                else window.train_range
            )
            return (
                run.backtest_start_date == date_range.start_date
                and run.backtest_end_date == date_range.end_date
            )

        return [
            r for r in runs
            if any(_run_matches(r, w) for w in windows_to_match)
        ]

    def populated_engines(self) -> List[str]:
        """Return the engine names whose slot has runs or a summary,
        in canonical order (``"vector"`` first).
        """
        out: List[str] = []
        for engine in ("vector", "event"):
            slot = self.engine_results.get(engine)
            if slot is not None and not slot.is_empty():
                out.append(engine)
        return out

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict for serialisation.

        Engines are emitted only when populated. Universe/windows are
        included even when empty so the round-trip is lossless.
        """
        return {
            "name": self.name,
            "description": self.description,
            "universe": self.universe.to_dict() if self.universe is not None else None,
            "backtest_windows": [
                bw.to_dict() for bw in (self.backtest_windows or [])
            ],
            "metadata": dict(self.metadata or {}),
            "monte_carlo_tests": [
                mct.to_dict()
                for mct in (self.monte_carlo_tests or [])
            ],
            "vector_runs": [
                r.to_dict() for r in self.get_runs(engine="vector")
            ],
            "vector_summary": self.get_summary(engine="vector").to_dict()
            if self.get_summary(engine="vector") is not None else None,
            "vector_summaries_by_universe": {
                k: s.to_dict()
                for k, s in (
                    (self.engine_results.get("vector") or EngineSlot())
                    .summaries_by_universe or {}
                ).items()
            },
            "event_runs": [
                r.to_dict() for r in self.get_runs(engine="event")
            ],
            "event_summary": self.get_summary(engine="event").to_dict()
            if self.get_summary(engine="event") is not None else None,
            "event_summaries_by_universe": {
                k: s.to_dict()
                for k, s in (
                    (self.engine_results.get("event") or EngineSlot())
                    .summaries_by_universe or {}
                ).items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Study":
        """Reconstruct a :class:`Study` from :meth:`to_dict` output."""
        if data is None:
            return None  # type: ignore[return-value]

        universe_raw = data.get("universe")

        if universe_raw is None:
            # Back-compat: older serialisations stored a list under "universes";
            # take the first entry.
            universes_list = data.get("universes") or []
            universe_raw = universes_list[0] if universes_list else None

        universe: Optional[Universe] = (
            Universe.from_dict(universe_raw)
            if universe_raw is not None else None
        )

        backtest_windows: List[BacktestWindow] = []
        for bw in (data.get("backtest_windows") or []):
            tr_raw = bw.get("train_range") or {}
            te_raw = bw.get("test_range")
            train_range = BacktestDateRange(
                start_date=tr_raw.get("start"),
                end_date=tr_raw.get("end"),
                name=tr_raw.get("name"),
            )
            test_range = (
                BacktestDateRange(
                    start_date=te_raw.get("start"),
                    end_date=te_raw.get("end"),
                    name=te_raw.get("name"),
                )
                if te_raw is not None else None
            )
            backtest_windows.append(BacktestWindow(
                train_range=train_range,
                test_range=test_range,
                warmup_days=bw.get("warmup_days", 0),
                fold_index=bw.get("fold_index"),
                name=bw.get("name"),
            ))

        # Decode engine slots from the flat format.
        engines: Dict[str, EngineSlot] = {}
        for engine_key, runs_key, summary_key, sbu_key in (
            ("vector", "vector_runs", "vector_summary", "vector_summaries_by_universe"),
            ("event", "event_runs", "event_summary", "event_summaries_by_universe"),
        ):
            runs = [
                BacktestRun.from_dict(r)
                for r in (data.get(runs_key) or [])
            ]
            summary_raw = data.get(summary_key)
            summary = (
                BacktestSummaryMetrics.from_dict(summary_raw)
                if summary_raw is not None else None
            )
            sbu_raw = data.get(sbu_key) or {}
            summaries_by_universe = {
                k: BacktestSummaryMetrics.from_dict(s)
                for k, s in sbu_raw.items()
                if s is not None
            }
            if runs or summary is not None or summaries_by_universe:
                engines[engine_key] = EngineSlot(
                    runs=runs,
                    summary=summary,
                    summaries_by_universe=summaries_by_universe,
                )

        monte_carlo_tests: List[BacktestMonteCarloTest] = [
            BacktestMonteCarloTest.from_dict(mct)
            for mct in (data.get("monte_carlo_tests") or [])
        ]

        return cls(
            name=data.get("name") or "default",
            description=data.get("description"),
            backtest_windows=backtest_windows,
            universe=universe,
            engine_results=engines,
            monte_carlo_tests=monte_carlo_tests,
            metadata=dict(data.get("metadata") or {}),
        )

    def __repr__(self) -> str:
        """
        Presentation string for the Study object, including its
        name, description, number of universes, number of windows,
        and populated engines.
        """
        return (
            f"Study(name={self.name!r}, description={self.description!r}, "
            f"universe={self.universe if self.universe else 'None'}, "
            f"windows={len(self.backtest_windows)}, "
            f"engines={self.populated_engines()})"
        )
