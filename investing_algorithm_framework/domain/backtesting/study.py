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

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union

from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)

from .backtest_monte_carlo_test import BacktestMonteCarloTest
from .backtest_run import BacktestRun
from .backtest_summary_metrics import BacktestSummaryMetrics
from .backtest_date_range import BacktestDateRange
from .backtest_window import BacktestWindow
from .universe import Universe
from .combine_backtests import generate_backtest_summary_metrics
from .backtest_engine import BacktestEngine
from .execution_config import ExecutionConfig

if TYPE_CHECKING:  # avoid a runtime circular import via .backtest
    from .backtest import Backtest


# Known ``sample_type`` values. The field also accepts free-form strings so
# users can attach custom tags without a framework change.
# See ``Study.sample_type`` and ``docs/design/backtest-bundle-format.md``.
class StudySampleType(str, Enum):
    IN_SAMPLE = "in_sample"
    OUT_SAMPLE_TIME = "out_sample_time"
    OUT_SAMPLE_UNIVERSE = "out_sample_universe"
    # Query-only meta-category (see Backtest.get_study_definitions):
    # matches any study tagged OUT_SAMPLE_TIME or OUT_SAMPLE_UNIVERSE.
    OUT_OF_SAMPLE = "out_of_sample"
    WALK_FORWARD = "walk_forward"
    STRESS = "stress"
    MONTE_CARLO = "monte_carlo"
    EXPLORATORY = "exploratory"

    def __str__(self) -> str:
        return self.value


SAMPLE_TYPE_IN_SAMPLE = StudySampleType.IN_SAMPLE.value
SAMPLE_TYPE_OUT_SAMPLE_TIME = StudySampleType.OUT_SAMPLE_TIME.value
SAMPLE_TYPE_OUT_SAMPLE_UNIVERSE = StudySampleType.OUT_SAMPLE_UNIVERSE.value
SAMPLE_TYPE_OUT_OF_SAMPLE = StudySampleType.OUT_OF_SAMPLE.value
SAMPLE_TYPE_WALK_FORWARD = StudySampleType.WALK_FORWARD.value
SAMPLE_TYPE_STRESS = StudySampleType.STRESS.value
SAMPLE_TYPE_MONTE_CARLO = StudySampleType.MONTE_CARLO.value
SAMPLE_TYPE_EXPLORATORY = StudySampleType.EXPLORATORY.value

KNOWN_SAMPLE_TYPES = (
    SAMPLE_TYPE_IN_SAMPLE,
    SAMPLE_TYPE_OUT_SAMPLE_TIME,
    SAMPLE_TYPE_OUT_SAMPLE_UNIVERSE,
    SAMPLE_TYPE_OUT_OF_SAMPLE,
    SAMPLE_TYPE_WALK_FORWARD,
    SAMPLE_TYPE_STRESS,
    SAMPLE_TYPE_MONTE_CARLO,
    SAMPLE_TYPE_EXPLORATORY,
)


class WindowPart(str, Enum):
    """Which part of each :class:`BacktestWindow` should actually be
    executed when a :class:`Study` is run.

    * ``TRAIN`` — only ``train_range`` (in-sample fit / sweep).
    * ``TEST`` — ``test_range``, falling back to ``train_range`` for
      windows that don't define a test range. This is the default.
    * ``BOTH`` — both ``train_range`` and ``test_range`` (each becomes
      its own run) for windows that define both.
    """

    TRAIN = "train"
    TEST = "test"
    BOTH = "both"

    def __str__(self) -> str:
        return self.value


KNOWN_WINDOW_PARTS = (
    WindowPart.TRAIN.value, WindowPart.TEST.value, WindowPart.BOTH.value,
)


@dataclass
class EngineSlot:
    """Per-engine container for runs, roll-up summaries and
    Monte-Carlo significance tests.

    Attributes:
        runs: Walk-forward runs produced by one engine for the
            owning :class:`Study`. Each run carries its own
            :class:`Universe` (the regime axis lives on the run,
            not the study).
        summary: Cross-window scalar roll-up pooled across **all**
            runs in this slot, irrespective of universe. ``None``
            when the slot is empty or hasn't been computed yet.
        monte_carlo_tests: Monte-Carlo significance tests produced
            by re-running this engine's strategy against permuted
            versions of its input data. Kept on the engine slot
            (not the study) because the null distribution is
            engine-specific: a vector-engine null and an
            event-engine null of the same strategy differ in fill
            / slippage semantics and their p-values are not
            interchangeable. See the OBTF Monte-Carlo test
            section.
    """

    runs: List[BacktestRun] = field(default_factory=list)
    summary: Optional[BacktestSummaryMetrics] = None
    summaries_by_universe: Dict[str, BacktestSummaryMetrics] = field(
        default_factory=dict
    )
    monte_carlo_tests: List[BacktestMonteCarloTest] = field(
        default_factory=list
    )

    def is_empty(self) -> bool:
        """Return True iff the slot carries no runs, no summary and
        no Monte-Carlo tests."""
        return (
            not self.runs
            and self.summary is None
            and not self.summaries_by_universe
            and not self.monte_carlo_tests
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
        sample_type: Optional categorical tag identifying the role
            this study plays in the evaluation workflow. Free-form
            to allow user-defined categories, but the framework
            recognises the following built-in values:

            * ``"in_sample"`` — plain in-sample fit or param sweep.
            * ``"out_sample_time"`` — time-based out-of-sample
              validation (same universe, later windows).
            * ``"out_sample_universe"`` — universe-based
              out-of-sample validation (different symbols / market).
            * ``"walk_forward"`` — rolling walk-forward with
              train/test splits.
            * ``"stress"`` — stress-test / parameter perturbation.
            * ``"monte_carlo"`` — Monte-Carlo scenario runs.
                        * ``"exploratory"`` — one-off experiment or visualization
                            that is not formal validation evidence.

            Consumers MUST treat unknown values as opaque strings.
            ``None`` means the runner did not tag the study (e.g.
            legacy bundles).
        execution_config: Optional snapshot of the cost / fill
            assumptions under which this study's runs were produced
            (blotter type, slippage / commission / fill models,
            per-symbol :class:`TradingCost` list). Round-trips into
            the bundle so downstream analysis can audit or reproduce
            the runs. ``None`` when the runner did not capture it
            (e.g. legacy bundles or a study that hasn't been run
            yet). See :mod:`.execution_config`.
        metadata: Free-form per-study metadata (e.g. provenance
            tags, parameter fingerprints, fold IDs).
        window_part: Which part of each :class:`BacktestWindow` to
            execute — one of ``"train"``, ``"test"`` (default) or
            ``"both"``. See :class:`WindowPart`. Used by
            :meth:`resolve_backtest_date_ranges` and by
            ``App.run_backtest``.
    """

    name: str = "default"
    description: Optional[str] = None
    backtest_windows: List[BacktestWindow] = field(default_factory=list)
    universe: Optional[Universe] = None # Probably is required
    # Client facing only, will not be persisted in the bundle.
    # Use engine_results for persisted data.
    engines: List[BacktestEngine] = field(default_factory=list)
    engine_results: Dict[str, EngineSlot] = field(default_factory=dict)
    initial_capital: Optional[float] = None
    risk_free_rate: Optional[float] = 0.027
    sample_type: Optional[Union[str, StudySampleType]] = None
    execution_config: Optional[ExecutionConfig] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    window_part: Union[str, WindowPart] = WindowPart.TEST.value
    # OHLCV price payload for this study. Keys are "<symbol>@<timeframe>"
    # (e.g. "BTC/EUR@1h"), values are pandas DataFrames. Populated when
    # the bundle was saved with ``include_ohlcv=True``. Not included in
    # JSON serialisation (handled at the bundle layer as Parquet blobs).
    ohlcv: Dict[str, object] = field(default_factory=dict, repr=False)

    @property
    def engine(self) -> Optional["BacktestEngine"]:
        """Return the first engine in ``self.engines``, or ``None`` if
        no engine has been configured."""
        return self.engines[0] if self.engines else None

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

    def copy_definition(self) -> "Study":
        """Return a copy of this study's configuration only.

        ``engine_results`` (runs, summaries, Monte-Carlo tests) is
        reset to empty; every other field (name, description,
        universe, backtest_windows, engines, etc.) is carried over.
        Useful for reusing an existing study's definition for a fresh
        run without dragging along its source runs.
        """
        return replace(self, engine_results={})

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
            candidates = [
                dr for dr in (window.train_range, window.test_range)
                if dr is not None
            ]
            return any(
                run.backtest_start_date == dr.start_date
                and run.backtest_end_date == dr.end_date
                for dr in candidates
            )

        return [
            r for r in runs
            if any(_run_matches(r, w) for w in windows_to_match)
        ]

    def resolve_backtest_date_ranges(self) -> List[BacktestDateRange]:
        """Resolve ``self.backtest_windows`` to the concrete date
        range(s) that should be executed, according to
        ``self.window_part``.

        * ``"train"`` \u2014 only each window's ``train_range``.
        * ``"test"`` (default) \u2014 each window's ``test_range``,
          falling back to ``train_range`` for train-only windows.
        * ``"both"`` \u2014 both ``train_range`` and ``test_range`` (each
          becomes its own run) for windows that define both.

        Returns:
            List[BacktestDateRange]: One entry per resolved range, in
                window order. Windows lacking the requested range are
                skipped.

        Raises:
            OperationalException: If ``window_part`` is not one of
                the known :class:`WindowPart` values.
        """
        part = (
            self.window_part.value
            if isinstance(self.window_part, WindowPart)
            else self.window_part
        )
        if part not in KNOWN_WINDOW_PARTS:
            raise OperationalException(
                f"Invalid Study.window_part '{part}'. "
                f"Must be one of {KNOWN_WINDOW_PARTS}."
            )

        ranges: List[BacktestDateRange] = []
        for window in (self.backtest_windows or []):
            if part == WindowPart.TRAIN.value:
                if window.train_range is not None:
                    ranges.append(window.train_range)
            elif part == WindowPart.BOTH.value:
                if window.train_range is not None:
                    ranges.append(window.train_range)
                if window.test_range is not None:
                    ranges.append(window.test_range)
            else:  # WindowPart.TEST.value
                resolved = (
                    window.test_range
                    if window.test_range is not None
                    else window.train_range
                )
                if resolved is not None:
                    ranges.append(resolved)
        return ranges

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

        Monte-Carlo tests are emitted per engine slot
        (``vector_monte_carlo_tests`` / ``event_monte_carlo_tests``)
        because a test's null distribution is engine-specific. See the
        OBTF Monte-Carlo test section in
        ``docs/architecture/backtest/open_backtest_format.md``.
        """
        vector_slot = self.engine_results.get("vector") or EngineSlot()
        event_slot = self.engine_results.get("event") or EngineSlot()
        return {
            "name": self.name,
            "description": self.description,
            "initial_capital": self.initial_capital,
            "risk_free_rate": self.risk_free_rate,
            "universe": self.universe.to_dict() if self.universe is not None else None,
            "backtest_windows": [
                bw.to_dict() for bw in (self.backtest_windows or [])
            ],
            "metadata": dict(self.metadata or {}),
            "sample_type": (
                self.sample_type.value
                if isinstance(self.sample_type, StudySampleType)
                else self.sample_type
            ),
            "window_part": (
                self.window_part.value
                if isinstance(self.window_part, WindowPart)
                else self.window_part
            ),
            "execution_config": (
                self.execution_config.to_dict()
                if self.execution_config is not None else None
            ),
            "vector_runs": [
                r.to_dict() for r in self.get_runs(engine="vector")
            ],
            "vector_summary": self.get_summary(engine="vector").to_dict()
            if self.get_summary(engine="vector") is not None else None,
            "vector_summaries_by_universe": {
                k: s.to_dict()
                for k, s in (vector_slot.summaries_by_universe or {}).items()
            },
            "vector_monte_carlo_tests": [
                mct.to_dict()
                for mct in (vector_slot.monte_carlo_tests or [])
            ],
            "event_runs": [
                r.to_dict() for r in self.get_runs(engine="event")
            ],
            "event_summary": self.get_summary(engine="event").to_dict()
            if self.get_summary(engine="event") is not None else None,
            "event_summaries_by_universe": {
                k: s.to_dict()
                for k, s in (event_slot.summaries_by_universe or {}).items()
            },
            "event_monte_carlo_tests": [
                mct.to_dict()
                for mct in (event_slot.monte_carlo_tests or [])
            ],
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
        for engine_key, runs_key, summary_key, sbu_key, mct_key in (
            (
                "vector", "vector_runs", "vector_summary",
                "vector_summaries_by_universe", "vector_monte_carlo_tests",
            ),
            (
                "event", "event_runs", "event_summary",
                "event_summaries_by_universe", "event_monte_carlo_tests",
            ),
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
            mc_tests = [
                BacktestMonteCarloTest.from_dict(mct)
                for mct in (data.get(mct_key) or [])
            ]
            if (
                runs
                or summary is not None
                or summaries_by_universe
                or mc_tests
            ):
                engines[engine_key] = EngineSlot(
                    runs=runs,
                    summary=summary,
                    summaries_by_universe=summaries_by_universe,
                    monte_carlo_tests=mc_tests,
                )

        # Back-compat: v4-era bundles stored a single ``monte_carlo_tests``
        # list at the study level (before MC tests were relocated onto
        # per-engine slots). Promote it onto the vector slot — the engine
        # that ``App.run_monte_carlo_test`` writes today.
        legacy_mct_raw = data.get("monte_carlo_tests")
        if (
            legacy_mct_raw
            and "vector_monte_carlo_tests" not in data
            and "event_monte_carlo_tests" not in data
        ):
            legacy_mcts = [
                BacktestMonteCarloTest.from_dict(mct)
                for mct in legacy_mct_raw
            ]
            v_slot = engines.setdefault("vector", EngineSlot())
            v_slot.monte_carlo_tests = (
                list(v_slot.monte_carlo_tests) + legacy_mcts
            )

        execution_config = ExecutionConfig.from_dict(
            data.get("execution_config")
        )

        return cls(
            name=data.get("name") or "default",
            description=data.get("description"),
            initial_capital=(
                data.get("initial_capital")
                or (universe_raw or {}).get("initial_capital")
            ),
            risk_free_rate=(
                data.get("risk_free_rate")
                or (universe_raw or {}).get("risk_free_rate")
                or 0.027
            ),
            backtest_windows=backtest_windows,
            universe=universe,
            engine_results=engines,
            sample_type=data.get("sample_type"),
            execution_config=execution_config,
            metadata=dict(data.get("metadata") or {}),
            window_part=data.get("window_part") or WindowPart.TEST.value,
        )

    def __repr__(self) -> str:
        """Return a bounded structural summary, including empty fields."""
        lines = [
            "Study(",
            f"  name={self.name!r},",
            f"  description={self.description!r},",
            f"  sample_type={self.sample_type!r},",
            f"  universe={self.universe!r},",
        ]

        if self.backtest_windows:
            lines.append("  backtest_windows=[")
            lines.extend(
                f"    {window!r}," for window in self.backtest_windows
            )
            lines.append("  ],")
        else:
            lines.append("  backtest_windows=[],")

        engine_types = [type(engine).__name__ for engine in self.engines]
        lines.append(f"  engines={engine_types!r},")
        lines.append("  engine_results={")

        engine_names = list(dict.fromkeys(
            ("vector", "event", *self.engine_results.keys())
        ))
        for engine_name in engine_names:
            slot = self.engine_results.get(engine_name)
            if slot is None:
                lines.append(f"    {engine_name!r}: <missing>,")
                continue

            summaries_by_universe = getattr(
                slot, "summaries_by_universe", {}
            ) or {}
            state = "empty" if slot.is_empty() else "populated"
            lines.extend([
                f"    {engine_name!r}: EngineSlot(",
                f"      state={state!r},",
                f"      runs={len(slot.runs)},",
                f"      summary={'present' if slot.summary is not None else None!r},",
                f"      summaries_by_universe={list(summaries_by_universe)!r},",
                f"      monte_carlo_tests={len(slot.monte_carlo_tests)},",
                "    ),",
            ])

        lines.extend([
            "  },",
            f"  execution_config={self.execution_config!r},",
            f"  metadata={self.metadata!r},",
            f"  ohlcv_keys={list(self.ohlcv)!r},",
            ")",
        ])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Study / universe stamping helpers
# ---------------------------------------------------------------------------
#
# These pure helpers reconcile a set of strategies against the universes a
# runner was launched with, and stamp the resulting study / universe / lineage
# fields onto ``Backtest`` objects before they are checkpointed to disk. Kept
# here rather than in a separate module so the "study" concept has a single
# home in the domain layer.

def build_strategy_universe_map(
    strategies: Iterable[Any],
    universes: Optional[List[Universe]],
) -> Dict[str, Universe]:
    """Match each strategy to exactly one :class:`Universe` by symbol subset.

    Returns a ``{algorithm_id: Universe}`` mapping. Each
    ``strategy.symbols`` must be a non-empty subset of exactly one
    universe's ``symbols`` list. When a strategy declares no symbols
    and exactly one universe is provided, that universe is used.

    Raises:
        OperationalException: if any universe key is missing or
            duplicated, if a strategy's symbols match no universe, or
            if a strategy declares no symbols while multiple universes
            are provided.
    """
    if not universes:
        return {}

    seen_keys: set = set()
    for u in universes:
        key = getattr(u, "key", None)
        if not key:
            raise OperationalException(
                "Every Universe passed to run_*_backtests must have a "
                "non-empty 'key'."
            )
        if key in seen_keys:
            raise OperationalException(
                f"Duplicate Universe key {key!r} — keys must be unique "
                "within a single run."
            )
        seen_keys.add(key)

    mapping: Dict[str, Universe] = {}
    for s in strategies:
        s_syms = set(getattr(s, "symbols", None) or [])
        if not s_syms:
            if len(universes) == 1:
                mapping[s.algorithm_id] = universes[0]
                continue
            raise OperationalException(
                f"Strategy {s.algorithm_id!r} declares no 'symbols' "
                "but multiple universes were provided. Either declare "
                "symbols on the strategy or pass exactly one universe."
            )

        matches = [
            u for u in universes
            if not u.symbols or s_syms.issubset(set(u.symbols))
        ]
        if len(matches) == 0:
            raise OperationalException(
                f"Strategy {s.algorithm_id!r} symbols {sorted(s_syms)} "
                "are not a subset of any provided universe. Universes: "
                + ", ".join(
                    f"{u.key}={list(u.symbols or [])}" for u in universes
                )
            )
        if len(matches) > 1:
            # Smallest matching universe wins (most specific).
            matches.sort(key=lambda u: len(u.symbols or []))
        mapping[s.algorithm_id] = matches[0]
    return mapping


def stamp_backtest(
    backtest: "Backtest",
    *,
    study_name: Optional[str] = None,
    study_description: Optional[str] = None,
    universe: Optional[Universe] = None,
    anchor_algorithm_id: Optional[str] = None,
    backtest_windows: Optional[List["BacktestWindow"]] = None,
    initial_capital: Optional[float] = None,
) -> None:
    """Stamp study fields and a single matched :class:`Universe` on a
    backtest in place.

    - Sets the default study's ``name`` / ``description`` if
      provided (``None`` leaves the existing value untouched).
    - When ``universe`` is provided, sets ``backtest.universes =
      [universe]``, tags every run with ``universe.key`` (without
      overwriting an existing tag) and regenerates the per-universe
      summaries.
    - Sets ``backtest.anchor_algorithm_id`` when provided (lineage
      edge to the in-sample winner this OOS run derives from).
    - When ``backtest_windows`` is provided (non-empty), stamps the
      full window list on the default study. This must happen on
      *every* checkpoint save (not just a final post-hoc pass over
      the survivors), otherwise a strategy eliminated mid-sweep by a
      progressive ``window_filter_function`` is checkpointed to disk
      with an empty ``backtest_windows`` and never corrected, since
      it never reaches the final survivor list.
    - When ``initial_capital`` is provided, stamps it on the default
      study for the same reason as ``backtest_windows`` above.

    Pure mutation, no I/O.
    """
    if study_name is not None:
        _ds = backtest.get_study()
        if _ds and _ds.name != study_name:
            backtest.rename_study(_ds.name, study_name)
    if study_description is not None:
        _ds = backtest.get_study()
        if _ds:
            _ds.description = study_description
    if universe is not None:
        backtest.universes = [universe]
        backtest.tag_runs_universe(universe.key, overwrite=False)
        backtest.regenerate_summaries_by_universe()
    if anchor_algorithm_id is not None:
        backtest.anchor_algorithm_id = anchor_algorithm_id
    if backtest_windows:
        _ds = backtest.get_study()
        if _ds:
            _ds.backtest_windows = list(backtest_windows)
    if initial_capital is not None:
        _ds = backtest.get_study()
        if _ds:
            _ds.initial_capital = initial_capital


def stamp_backtests(
    backtests: Iterable["Backtest"],
    *,
    study_name: Optional[str] = None,
    study_description: Optional[str] = None,
    universe_map: Optional[Dict[str, Universe]] = None,
    anchor_algorithm_id: Optional[str] = None,
    backtest_windows: Optional[List["BacktestWindow"]] = None,
    initial_capital: Optional[float] = None,
) -> None:
    """Apply :func:`stamp_backtest` to every backtest in an iterable.

    ``universe_map`` is keyed by ``algorithm_id``. Backtests whose id
    is not in the map are stamped with ``universe=None`` (study fields
    only). ``anchor_algorithm_id``, ``backtest_windows`` and
    ``initial_capital`` are applied uniformly to every backtest in the
    iterable.
    """
    if (
        study_name is None
        and study_description is None
        and not universe_map
        and anchor_algorithm_id is None
        and not backtest_windows
        and initial_capital is None
    ):
        return
    for bt in backtests:
        u = universe_map.get(bt.algorithm_id) if universe_map else None
        stamp_backtest(
            bt,
            study_name=study_name,
            study_description=study_description,
            universe=u,
            anchor_algorithm_id=anchor_algorithm_id,
            backtest_windows=backtest_windows,
            initial_capital=initial_capital,
        )
