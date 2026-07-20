import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from logging import getLogger
from typing import Dict, Union, List, Optional, TYPE_CHECKING

from investing_algorithm_framework.domain.exceptions \
    import OperationalException

from .backtest_metrics import BacktestMetrics
from .backtest_run import BacktestRun
from .backtest_monte_carlo_test import BacktestMonteCarloTest
from .backtest_date_range import BacktestDateRange
from .backtest_summary_metrics import BacktestSummaryMetrics
from .backtest_index_row import BacktestIndexRow
from .combine_backtests import generate_backtest_summary_metrics
from .universe import Universe
from .study import Study as _Study, EngineSlot  # noqa: WPS433

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .study import Study


logger = getLogger(__name__)


# Valid engine identifiers used throughout the v9.0 dual-engine model.
# Exposed as module-level constants so other modules (bundle reader,
# SQLite index, report builder) can import a single source of truth.
ENGINE_VECTOR = "vector"
ENGINE_EVENT = "event"
ENGINES = (ENGINE_VECTOR, ENGINE_EVENT)


def _regenerate_summary(
    runs: List[BacktestRun],
) -> Optional[BacktestSummaryMetrics]:
    """Re-derive a :class:`BacktestSummaryMetrics` from a list of runs.

    Returns ``None`` when the run list is empty or has no runs that
    carry per-run :class:`BacktestMetrics`. Used by both :meth:`merge`
    and the directory save path to keep summaries in sync with the
    current runs.
    """
    if not runs:
        return None
    per_run_metrics = [
        br.backtest_metrics for br in runs
        if br.backtest_metrics is not None
    ]
    if not per_run_metrics:
        return None
    return generate_backtest_summary_metrics(per_run_metrics)


def _filter_runs_by_date_ranges(
    runs: List[BacktestRun],
    date_ranges: List[BacktestDateRange],
) -> List[BacktestRun]:
    """Return the subset of ``runs`` whose date range matches one of
    ``date_ranges``. Preserves the input ordering of ``runs``."""
    if not runs:
        return []
    filtered: List[BacktestRun] = []
    for run in runs:
        for dr in date_ranges:
            if (run.backtest_start_date == dr.start_date
                    and run.backtest_end_date == dr.end_date):
                filtered.append(run)
                break
    return filtered


def _filter_engine_slots_in_place(
    bt: 'Backtest',
    date_ranges: List[BacktestDateRange],
) -> None:
    """Apply a date-range filter to both engine slots of ``bt``,
    mutating in place. Empty slots are left empty."""
    for study in bt._studies.values():
        for engine in ENGINES:
            slot = study.engine_results.get(engine)
            if slot is not None:
                slot.runs = _filter_runs_by_date_ranges(
                    slot.runs or [], date_ranges
                )


@dataclass(init=False)
class Backtest:
    """A backtest report for one algorithm, holding results from either
    or both engines (vectorized and event-based).

    A :class:`Backtest` is the canonical in-memory representation of
    one ``.iafbt`` bundle file. As of v9.0 it carries two independent
    engine slots — a bundle may contain vector-engine results, event-
    engine results, or both. See ``docs/design/v9.0-dual-engine-design.md``
    for the binding contract.

    Attributes:
        algorithm_id: The ID of the algorithm this backtest is for.
            Identifies the strategy / config being measured.
        anchor_algorithm_id: Optional lineage pointer for sibling
            bundles. ``None`` for primary / anchor bundles. Set to
            the anchor's ``algorithm_id`` on derived bundles such as
            param-robustness perturbations or cooldown-stress runs,
            so a single SQL ``GROUP BY anchor_algorithm_id`` query
            recovers the entire neighbourhood of a champion. v5+.

        metadata: Free-form bundle metadata (algorithm config notes,
            framework version, migration provenance, etc.). Shared
            across engines.

        strategy_ids: IDs of the strategies that make up the algorithm.
            Shared across engines.
        parameters: The algorithm's hyperparameters. Shared.
        tag: Optional user-supplied label. Shared.
        _studies: Dict of Study objects, keyed by study name. Each study holds
    """
    algorithm_id: str
    anchor_algorithm_id: Optional[str] = None
    backtest_id: Optional[str] = None
    framework_version: Optional[str] = None
    bundle_format_version: Optional[int] = None
    tag: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    strategy_ids: List = field(default_factory=list)
    parameters: Dict = field(default_factory=dict)

    _studies: Dict[str, "Study"] = field(
        default_factory=dict, init=False, repr=False,
    )

    def __init__(
        self,
        algorithm_id: str,
        anchor_algorithm_id: Optional[str] = None,
        backtest_id: Optional[str] = None,
        framework_version: Optional[str] = None,
        bundle_format_version: Optional[int] = None,
        tag: Optional[str] = None,
        metadata: Optional[Dict] = None,
        strategy_ids: Optional[List] = None,
        parameters: Optional[Dict] = None,
        # Backward-compat kwargs — wrap into a default study on construction.
        vector_runs=None,
        event_runs=None,
        backtest_summary=None,
        backtest_monte_carlo_tests=None,
        risk_free_rate=None,
        vector_summary=None,
        event_summary=None,
        study_name=None,
        study_description=None,
        universes=None,
        vector_summaries_by_universe=None,
        event_summaries_by_universe=None,
    ) -> None:
        self.algorithm_id = algorithm_id
        self.anchor_algorithm_id = anchor_algorithm_id
        self.backtest_id = backtest_id
        self.framework_version = framework_version
        self.bundle_format_version = bundle_format_version
        self.tag = tag
        self.metadata = metadata if metadata is not None else {}
        self.strategy_ids = strategy_ids if strategy_ids is not None else []
        self.parameters = parameters if parameters is not None else {}
        self._studies: Dict[str, "_Study"] = {}
        # Universe catalogue for the primary/default study context.
        # Populated from the ``universes`` compat kwarg; returned by the
        # ``universes`` property when non-empty.
        self._universe_catalogue: List = []

        # Build a default study from legacy flat kwargs when supplied.
        if any(
            v is not None for v in (
                vector_runs, event_runs, backtest_summary,
                backtest_monte_carlo_tests, risk_free_rate,
                vector_summary, event_summary, study_name,
                study_description, universes,
            )
        ):
            from .universe import Universe as _U
            _sname = study_name or "default"
            default_study = _Study(name=_sname, description=study_description)

            # Universe handling
            if universes:
                # Normalise dict→Universe
                _univs = [
                    _U.from_dict(u) if isinstance(u, dict) else u
                    for u in universes
                ]
                default_study.universe = _univs[0]
                # Store the full catalogue so bt.universes returns all of them.
                self._universe_catalogue = list(_univs)
            if risk_free_rate is not None:
                if default_study.universe is None:
                    default_study.universe = _U(risk_free_rate=risk_free_rate)
                else:
                    default_study.universe.risk_free_rate = risk_free_rate

            # Vector slot
            if any(v is not None for v in (
                vector_runs, vector_summary, backtest_summary,
                vector_summaries_by_universe,
            )):
                v_slot = default_study.get_engine(ENGINE_VECTOR)
                if vector_runs is not None:
                    v_slot.runs = list(vector_runs)
                if vector_summary is not None:
                    v_slot.summary = vector_summary
                elif backtest_summary is not None:
                    v_slot.summary = backtest_summary
                if vector_summaries_by_universe:
                    v_slot.summaries_by_universe = dict(
                        vector_summaries_by_universe
                    )

            # Event slot
            if any(v is not None for v in (
                event_runs, event_summary, event_summaries_by_universe,
            )):
                e_slot = default_study.get_engine(ENGINE_EVENT)
                if event_runs is not None:
                    e_slot.runs = list(event_runs)
                if event_summary is not None:
                    e_slot.summary = event_summary
                if event_summaries_by_universe:
                    e_slot.summaries_by_universe = dict(
                        event_summaries_by_universe
                    )

            if backtest_monte_carlo_tests is not None:
                default_study.monte_carlo_tests = list(
                    backtest_monte_carlo_tests
                )
            self._studies[_sname] = default_study

    def _get_default_study(self) -> Optional["Study"]:
        """Return the first (default) study, or ``None`` when empty."""
        if not self._studies:
            return None
        return next(iter(self._studies.values()))

    def _get_or_create_default_study(self) -> "Study":
        """Return the default study, creating one named ``"default"`` if needed."""
        if not self._studies:
            self._studies["default"] = _Study(name="default")
        return next(iter(self._studies.values()))

    def _require_single_study(self, context: str = "") -> Optional["Study"]:
        """Enforce the default-study rule.

        * 0 studies → returns ``None``.
        * 1 study  → returns it.
        * 2+ studies → raises :class:`OperationalException`.
        """
        n = len(self._studies)
        if n == 0:
            return None
        if n == 1:
            return self._get_default_study()
        raise OperationalException(
            f"Backtest has {n} studies — pass study= to disambiguate"
            + (f" ({context})" if context else "") + "."
        )

    def get_runs(
        self, engine: str, study: Optional[str] = None,
    ) -> List[BacktestRun]:
        """Return the runs for the given engine, optionally scoped to a
        specific study slot.

        Args:
            engine: One of ``"vector"`` or ``"event"``.
            study: Optional study name. When omitted (default), follows
                the **default-study rule** documented in
                ``docs/design/multi-study-bundle.md`` §4.3:

                * single study → returns its runs (the legacy single-
                  bundle behaviour);
                * zero or multiple studies →
                  :class:`OperationalException`. Pass an explicit
                  ``study=`` to disambiguate.

                When ``study`` is provided, returns only the runs
                belonging to that study slot. ``None`` is returned
                when the slot exists but the engine isn't populated
                for it (the caller can distinguish from
                ``KeyError`` via :meth:`get_study`).

        Raises:
            ValueError: If ``engine`` is not a recognised engine.
            OperationalException: If the default-study rule rejects
                the call.
        """
        if engine not in ENGINES:
            raise ValueError(
                f"Unknown engine {engine!r}, expected one of "
                f"{list(ENGINES)}."
            )
        if study is None:
            st = self._require_single_study("get_runs()")
            if st is None:
                return []
            return st.get_runs(engine)

        st = self.get_study(study)
        if st is None:
            raise OperationalException(
                f"No study {study!r}. Available: {self.list_studies()!r}."
            )
        return st.get_runs(engine)

    def get_summary(
        self, engine: str, study: Optional[str] = None,
    ) -> Optional[BacktestSummaryMetrics]:
        """Return the summary metrics for the given engine, optionally
        scoped to a specific study slot.

        Args:
            engine: One of ``"vector"`` or ``"event"``.
            study: Optional study name. When omitted (default), follows
                the **default-study rule** documented in
                ``docs/design/multi-study-bundle.md`` §4.3:

                * single study → returns its summary;
                * zero or multiple studies →
                  :class:`OperationalException`. Pass an explicit
                  ``study=``.

                When ``study`` is provided, returns the per-universe
                summary for that study slot.

        Raises:
            ValueError: If ``engine`` is not a recognised engine.
            OperationalException: If the default-study rule rejects
                the call, or the named study doesn't exist.
        """
        if engine not in ENGINES:
            raise ValueError(
                f"Unknown engine {engine!r}, expected one of "
                f"{list(ENGINES)}."
            )
        if study is None:
            st = self._require_single_study("get_summary()")
            if st is None:
                return None
            return st.get_summary(engine)

        st = self.get_study(study)
        if st is None:
            raise OperationalException(
                f"No study {study!r}. Available: {self.list_studies()!r}."
            )
        return st.get_summary(engine)

    @property
    def studies(self) -> Dict[str, "Study"]:
        """Return the ``{study_name: Study}`` mapping.

        After the ERD alignment refactor, ``_studies`` is the canonical
        store. This property provides public read-only access.
        """
        return self._studies

    def list_studies(self) -> List[str]:
        """Return the names of all studies currently visible on this
        :class:`Backtest`, in canonical order.
        """
        return list(self.studies.keys())

    def get_study(self, name=None) -> Optional["Study"]:
        """Return the named :class:`Study`, or the first study when
        *name* is ``None``.  Returns ``None`` when no matching study
        exists (or the backtest has no studies at all).

        *name* may be a ``str`` or a :class:`Study` instance (the
        instance's ``.name`` attribute is used in that case).
        """
        if name is None:
            return self._get_default_study()
        # Accept Study objects — extract the name string so dict lookup works.
        if hasattr(name, "name"):
            name = name.name
        return self.studies.get(name)

    def rename_study(self, old_name: str, new_name: str) -> None:
        """Rename a study, re-keying it in the ``_studies`` dict."""
        study = self._studies.pop(old_name, None)
        if study is None:
            return
        study.name = new_name
        # Preserve insertion order: rebuild the dict with the new key
        # in the same position as the old one.
        new_dict = {}
        for k, v in self._studies.items():
            new_dict[k] = v
        new_dict[new_name] = study
        self._studies.clear()
        self._studies.update(new_dict)

    def get_studies(self) -> List[Dict[str, object]]:
        """Return a summary of every study contained in this backtest.

        This is the human-friendly counterpart of :meth:`list_studies`
        (names only) and the :pyattr:`studies` view (full
        :class:`Study` objects). It walks :pyattr:`studies` and emits a
        plain ``dict`` per study so callers (notebooks, CLIs, reports)
        can introspect the bundle without importing the
        :class:`Study` type.

        Each dict contains:

        * ``name`` (``str``): study identifier.
        * ``description`` (``Optional[str]``): free-form description.
        * ``engines`` (``List[str]``): populated engines for this
          study, in canonical order (vector first).
        * ``n_runs`` (``Dict[str, int]``): number of runs per
          populated engine.
        * ``universes`` (``List[str]``): keys of the universes this
          study has runs/registry entries for.
        * ``n_windows`` (``int``): number of date-range windows the
          study spans.

        Returns:
            List[Dict[str, object]]: One entry per study, in the order
                returned by :meth:`list_studies` (default/legacy slot
                first, then additional studies in insertion order).
        """
        out: List[Dict[str, object]] = []
        for name, study in self.studies.items():
            engines = study.populated_engines()
            n_runs = {
                engine: len(study.get_runs(engine)) for engine in engines
            }
            out.append({
                "name": name,
                "description": study.description,
                "engines": engines,
                "n_runs": n_runs,
                "universes": [study.universe.key] if study.universe else [],
                "n_windows": len(study.windows),
            })
        return out

    def add_study(self, study: "Study") -> None:
        """Append a new study to this backtest.

        Every named study lives in its own slot in ``_studies``.

        Raises:
            OperationalException: If a study with the same name is
                already present on this :class:`Backtest`.
            TypeError: If ``study`` is not a :class:`Study`.
        """
        from .study import Study as _Study  # noqa: WPS433

        if not isinstance(study, _Study):
            raise TypeError(
                f"add_study expects a Study instance, got "
                f"{type(study).__name__}."
            )

        if study.name in self._studies:
            raise OperationalException(
                f"Study {study.name!r} already exists on this Backtest."
            )

        self._studies[study.name] = study

    # ------------------------------------------------------------------
    # Convenience properties / methods that callers (services, tests,
    # notebooks) use to access v9.0 data through the Study model.
    # ------------------------------------------------------------------

    @property
    def risk_free_rate(self) -> Optional[float]:
        """Read the risk-free rate from the default study's universe."""
        st = self._get_default_study()
        if st is not None and st.universe is not None:
            return st.universe.risk_free_rate
        return None

    @risk_free_rate.setter
    def risk_free_rate(self, value: Optional[float]) -> None:
        """Store the risk-free rate on the default study's universe."""
        st = self._get_or_create_default_study()
        if st.universe is None:
            st.universe = Universe(risk_free_rate=value)
        else:
            st.universe.risk_free_rate = value

    @property
    def vector_runs(self) -> List:
        """Backward-compat: vector runs from the default (first) study."""
        st = self._get_default_study()
        return st.get_runs(ENGINE_VECTOR) if st is not None else []

    @vector_runs.setter
    def vector_runs(self, value) -> None:
        """Backward-compat: set vector runs on the default study."""
        st = self._get_or_create_default_study()
        st.get_engine(ENGINE_VECTOR).runs = list(value) if value is not None else []

    @property
    def event_runs(self) -> List:
        """Backward-compat: event runs from the default (first) study."""
        st = self._get_default_study()
        return st.get_runs(ENGINE_EVENT) if st is not None else []

    @event_runs.setter
    def event_runs(self, value) -> None:
        """Backward-compat: set event runs on the default study."""
        st = self._get_or_create_default_study()
        st.get_engine(ENGINE_EVENT).runs = list(value) if value is not None else []

    def engines(self) -> List[str]:
        """Return the engine names that have at least one run or summary across
        all studies, in canonical order (vector first, then event)."""
        found: List[str] = []
        for engine in ENGINES:
            for st in self._studies.values():
                slot = st.engine_results.get(engine)
                if slot is not None and not slot.is_empty():
                    found.append(engine)
                    break
        return found

    @property
    def vector_summary(self) -> Optional["BacktestSummaryMetrics"]:
        """Shortcut: summary for the vector engine of the default study."""
        st = self._get_default_study()
        return st.get_summary(ENGINE_VECTOR) if st is not None else None

    @vector_summary.setter
    def vector_summary(self, value: Optional["BacktestSummaryMetrics"]) -> None:
        slot = self._get_or_create_default_study().get_engine(ENGINE_VECTOR)
        slot.summary = value

    @property
    def event_summary(self) -> Optional["BacktestSummaryMetrics"]:
        """Shortcut: summary for the event engine of the default study."""
        st = self._get_default_study()
        return st.get_summary(ENGINE_EVENT) if st is not None else None

    @event_summary.setter
    def event_summary(self, value: Optional["BacktestSummaryMetrics"]) -> None:
        slot = self._get_or_create_default_study().get_engine(ENGINE_EVENT)
        slot.summary = value

    @property
    def backtest_monte_carlo_tests(self) -> List[BacktestMonteCarloTest]:
        """Shortcut: monte carlo tests of the default study."""
        st = self._get_default_study()
        return st.monte_carlo_tests if st is not None else []

    @backtest_monte_carlo_tests.setter
    def backtest_monte_carlo_tests(
        self, value: List[BacktestMonteCarloTest]
    ) -> None:
        self._get_or_create_default_study().monte_carlo_tests = list(
            value or []
        )

    @property
    def vector_summaries_by_universe(self) -> Dict:
        """Backward-compat: per-universe summaries from the default study's vector slot."""
        st = self._get_default_study()
        if st is None:
            return {}
        slot = st.engine_results.get(ENGINE_VECTOR)
        return slot.summaries_by_universe if slot is not None else {}

    @vector_summaries_by_universe.setter
    def vector_summaries_by_universe(self, value: Dict) -> None:
        self._get_or_create_default_study().get_engine(
            ENGINE_VECTOR
        ).summaries_by_universe = dict(value) if value else {}

    @property
    def event_summaries_by_universe(self) -> Dict:
        """Backward-compat: per-universe summaries from the default study's event slot."""
        st = self._get_default_study()
        if st is None:
            return {}
        slot = st.engine_results.get(ENGINE_EVENT)
        return slot.summaries_by_universe if slot is not None else {}

    @event_summaries_by_universe.setter
    def event_summaries_by_universe(self, value: Dict) -> None:
        self._get_or_create_default_study().get_engine(
            ENGINE_EVENT
        ).summaries_by_universe = dict(value) if value else {}

    @property
    def universes(self) -> List["Universe"]:
        """Universe catalogue for the primary/default study context.

        Returns the ``_universe_catalogue`` when populated (e.g. from
        the backward-compat ``universes=`` constructor kwarg).  Falls
        back to collecting the default study's universe (one entry),
        so callers always get a list.
        """
        if self._universe_catalogue:
            return list(self._universe_catalogue)
        st = self._get_default_study()
        if st is not None and st.universe is not None:
            return [st.universe]
        return []

    @universes.setter
    def universes(self, value: List["Universe"]) -> None:
        self._universe_catalogue = list(value) if value else []
        # Also update the default study's primary universe.
        if value:
            self._get_or_create_default_study().universe = value[0]
        else:
            st = self._get_default_study()
            if st is not None:
                st.universe = None

    def tag_runs_universe(
        self, key: str, overwrite: bool = False, engines: list = None
    ) -> None:
        """Tag every run in every study with the given universe key."""
        _engines = engines if engines is not None else list(ENGINES)
        for st in self._studies.values():
            all_runs = []
            for eng in _engines:
                all_runs.extend(st.get_runs(eng))
            for run in all_runs:
                if overwrite or (run.metadata or {}).get("universe_key") is None:
                    if not hasattr(run, "metadata") or run.metadata is None:
                        run.metadata = {}
                    run.metadata["universe_key"] = key

    def regenerate_summaries(self) -> None:
        """Recompute per-engine summaries for every study from current runs."""
        for st in self._studies.values():
            for engine in ENGINES:
                slot = st.engine_results.get(engine)
                if slot is None:
                    continue
                runs = slot.runs or []
                if not runs:
                    slot.summary = None
                else:
                    regen = _regenerate_summary(runs)
                    if regen is not None:
                        slot.summary = regen

    def regenerate_summaries_by_universe(self) -> None:
        """Recompute per-universe summaries inside every study's engine slots."""
        for st in self._studies.values():
            for engine in ENGINES:
                slot = st.engine_results.get(engine)
                if slot is None:
                    continue
                by_universe: Dict[str, List] = {}
                for run in slot.runs or []:
                    uk = (run.metadata or {}).get("universe_key")
                    if uk is None:
                        continue
                    by_universe.setdefault(uk, []).append(run)
                slot.summaries_by_universe = {
                    uk: _regenerate_summary(runs)
                    for uk, runs in by_universe.items()
                    if runs
                }

    def get_all_backtest_monte_carlo_tests(
        self,
    ) -> List[BacktestMonteCarloTest]:
        """Return all monte carlo tests across all studies."""
        result: List[BacktestMonteCarloTest] = []
        for st in self._studies.values():
            result.extend(st.monte_carlo_tests)
        return result

    def get_all_backtest_runs(
        self, backtest_date_ranges=None, study=None, study_name=None,
    ) -> List[BacktestRun]:
        """
        Retrieve all BacktestRun instances from the backtest, across
        both engines.

        Vector runs are returned first, then event runs.

        Args:
            backtest_date_ranges (List[BacktestDateRange], optional): A list of
                date ranges to filter the backtest runs. If provided, only
                runs matching one of the date ranges are returned.

        Returns:
            List[BacktestRun]: All BacktestRun instances, vector first.
        """
        scope = study or study_name
        if scope is not None:
            st = self.get_study(scope)
            studies = [st] if st is not None else []
        else:
            studies = list(self._studies.values())

        all_runs: List[BacktestRun] = []
        for st in studies:
            all_runs += list(st.get_runs(ENGINE_VECTOR))
            all_runs += list(st.get_runs(ENGINE_EVENT))

        if backtest_date_ranges is not None:
            filtered_runs = []
            for date_range in backtest_date_ranges:
                for run in all_runs:
                    if (run.backtest_start_date == date_range.start_date
                            and run.backtest_end_date == date_range.end_date):
                        filtered_runs.append(run)
                        break
            return filtered_runs

        return all_runs

    def get_backtest_run(
        self,
        window: Union["BacktestWindow", BacktestDateRange],
        engine: Union[str, None] = None,
        study: Union[str, None] = None,
    ) -> Union[BacktestRun, None]:
        """
        Retrieve a specific BacktestRun based on a window or date range.

        Args:
            window: A :class:`BacktestWindow` or a
                :class:`BacktestDateRange`. When a ``BacktestWindow`` is
                provided, the execution range is resolved as
                ``window.test_range`` when present, otherwise
                ``window.train_range`` (mirrors how the engine keys runs).
            engine (str | None): Which engine slot to search. One of
                ``"vector"``, ``"event"``, or ``None``. When ``None``
                (default) the vector engine's runs are searched first,
                then the event engine.
            study (str | None): Optional study name to scope the search
                to a specific study's runs.

        Returns:
            Union[BacktestRun, None]: The matching BacktestRun if found,
                otherwise None.
        """
        # Resolve to a BacktestDateRange regardless of input type.
        if isinstance(window, BacktestDateRange):
            date_range = window
        else:
            date_range = (
                window.test_range
                if window.test_range is not None
                else window.train_range
            )

        if study is not None:
            runs = self.get_runs(engine or "vector", study=study)
            if engine is None:
                runs = list(runs) + list(
                    self.get_runs("event", study=study)
                )
            for run in runs:
                if (run.backtest_start_date == date_range.start_date and
                        run.backtest_end_date == date_range.end_date):
                    return run
            return None

        engines_to_search = [engine] if engine else list(ENGINES)
        for eng in engines_to_search:
            for run in self.get_runs(eng):
                if (run.backtest_start_date == date_range.start_date and
                        run.backtest_end_date == date_range.end_date):
                    return run
        return None

    def get_backtest_monte_carlo_test(
        self, date_range: BacktestDateRange
    ) -> Union[BacktestMonteCarloTest, None]:
        st = self._get_default_study()
        if st is None:
            return None
        for mc in st.monte_carlo_tests:
            if (mc.backtest_start_date == date_range.start_date and
                    mc.backtest_end_date == date_range.end_date):
                return mc
        return None

    def get_all_backtest_metrics(self) -> List[BacktestMetrics]:
        return [
            run.backtest_metrics
            for run in self.get_all_backtest_runs()
            if run.backtest_metrics is not None
        ]

    def get_backtest_metrics(
        self,
        date_range: BacktestDateRange,
        engine: Union[str, None] = None,
        study: Union[str, None] = None,
        study_name: Union[str, None] = None,
    ) -> Union[BacktestMetrics, None]:
        run = self.get_backtest_run(
            date_range, engine=engine, study=study or study_name
        )
        if run is None:
            return None
        return run.backtest_metrics

    def index_rows(
        self, bundle_path: Union[str, None] = None,
    ) -> List[BacktestIndexRow]:
        """Return one :class:`BacktestIndexRow` per (study, engine),
        plus per-(study, engine, universe) rows for studies that
        carry per-universe summaries.

        Row shape:

        * **Pooled rows** (``universe_key=None``) — one per populated
          engine *per study*, summary = the cross-universe pooled
          summary, ``number_of_runs`` = total runs for that engine
          slot. This preserves the v9.0 single-engine contract for
          single-study bundles.
        * **Per-universe rows** — emitted only when a study's engine
          slot carries ``summaries_by_universe``. One row per
          (study, engine, universe_key) with the per-universe summary
          and the count of runs whose ``metadata["universe_key"]``
          equals that key.

        ``study_name`` is stamped on every row from the owning study
        slot (Phase 3d). Each study's own ``name`` is used directly.
        No heavy time-series data is touched — these rows can be
        built from a bundle opened with
        ``Backtest.open(path, summary_only=True)``.

        Args:
            bundle_path: Optional location the bundle was loaded from
                (relative or absolute). Stored verbatim on every row.

        Returns:
            List[BacktestIndexRow]: Rows ordered by study (legacy
                default first, then additional studies in insertion
                order), then by engine (vector before event), pooled
                rows before per-universe rows within each engine.

        See also:
            ``docs/design/v9.0-dual-engine-design.md`` §6.
            ``docs/design/tiered-backtest-storage.md`` §3.1.
            ``docs/design/multi-study-bundle.md`` §4.3 / Phase 3d.
        """
        rows: List[BacktestIndexRow] = []

        common_kwargs = dict(
            algorithm_id=self.algorithm_id,
            anchor_algorithm_id=self.anchor_algorithm_id,
            tag=self.tag,
            bundle_path=bundle_path,
        )

        for study_name, study in self.studies.items():
            # risk_free_rate is now owned by Universe; fall back to the
            # backtest-level override for legacy bundles without a universe.
            study_rfr = (
                study.universe.risk_free_rate
                if study.universe is not None
                else None
            )
            study_kwargs = dict(common_kwargs)
            study_kwargs["study_description"] = study.description
            study_kwargs["study_name"] = study_name
            study_kwargs["risk_free_rate"] = study_rfr

            for engine, slot in study.engine_results.items():
                runs = slot.runs or []
                summary = slot.summary
                if not runs and summary is None:
                    continue
                rows.append(
                    BacktestIndexRow(
                        engine_type=engine,
                        parameters=dict(self.parameters or {}),
                        strategy_ids=list(self.strategy_ids or []),
                        number_of_runs=len(runs),
                        summary_metrics=summary,
                        universe_key=None,
                        **study_kwargs,
                    )
                )

            # Per-universe rows for this study.
            for engine, slot in study.engine_results.items():
                per_universe = slot.summaries_by_universe or {}
                if not per_universe:
                    continue
                counts: Dict[str, int] = {}
                for run in (slot.runs or []):
                    key = (run.metadata or {}).get("universe_key")
                    if key:
                        counts[key] = counts.get(key, 0) + 1
                for universe_key, summary in per_universe.items():
                    rows.append(
                        BacktestIndexRow(
                            engine_type=engine,
                            parameters=dict(self.parameters or {}),
                            strategy_ids=list(self.strategy_ids or []),
                            number_of_runs=counts.get(universe_key, 0),
                            summary_metrics=summary,
                            universe_key=universe_key,
                            **study_kwargs,
                        )
                    )

        return rows

    def to_dict(self) -> dict:
        """Convert the Backtest instance to a dictionary.

        Canonical v9.0 shape: shared scalar fields at the top level,
        all studies serialized in a ``studies`` dict keyed by study name.
        Each study carries its own engine slots, universe, windows and
        Monte-Carlo tests — there are no flat ``vector_runs`` /
        ``study_name`` / ``extra_studies`` keys.

        Returns:
            dict: A dictionary representation of the Backtest instance.
        """
        d = {
            "algorithm_id": self.algorithm_id,
            "anchor_algorithm_id": self.anchor_algorithm_id,
            "metadata": self.metadata,
            "strategy_ids": self.strategy_ids,
            "parameters": self.parameters,
            "tag": self.tag,
            "studies": {
                name: study.to_dict()
                for name, study in self._studies.items()
            },
        }
        cat = getattr(self, "_universe_catalogue", [])
        if cat:
            d["universes"] = [
                u.to_dict() if hasattr(u, "to_dict") else u
                for u in cat
            ]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'Backtest':
        """Reconstruct a ``Backtest`` from a plain dict.

        Accepts the v9.0 canonical shape (``studies`` dict) and the
        previous hybrid shape (flat engine slots + ``extra_studies``)
        for backward compatibility with persisted bundles.
        """
        if data is None:
            return None

        inst = cls(algorithm_id=data.get("algorithm_id"))
        inst.anchor_algorithm_id = data.get("anchor_algorithm_id")
        inst.metadata = data.get("metadata") or {}
        inst.strategy_ids = data.get("strategy_ids") or []
        inst.parameters = data.get("parameters") or {}
        inst.tag = data.get("tag")
        # Ensure catalogue is always present even on objects restored via
        # this path (cls() initialises it, but an explicit guard is cheap).
        if not hasattr(inst, "_universe_catalogue"):
            inst._universe_catalogue = []
        for name, study_raw in (data.get("studies") or {}).items():
            if study_raw is None:
                continue
            inst._studies[name] = _Study.from_dict(study_raw)

        # Restore universe catalogue when studies are present (v9.0 round-trip)
        if inst._studies and data.get("universes"):
            from .universe import Universe as _Universe
            inst._universe_catalogue = [
                _Universe.from_dict(u) if isinstance(u, dict) else u
                for u in data["universes"]
            ]

        # Legacy / bundle-reader flat fields: vector_runs, event_runs,
        # vector_summary, event_summary, extra_studies, universes,
        # risk_free_rate.  These come from the v3-v4 bundle readers and
        # _v5_envelope_to_backtest which flatten study data before
        # calling from_dict. Ignore them when studies are already set.
        if not inst._studies:
            _vr = data.get("vector_runs") or []
            _er = data.get("event_runs") or []
            _vs = data.get("vector_summary")
            _es = data.get("event_summary")
            _mc = data.get("backtest_monte_carlo_tests") or []
            _univ_raw = data.get("universes") or []
            _rfr = data.get("risk_free_rate")
            _study_name = data.get("study_name") or "default"
            _study_desc = data.get("study_description")
            _vsu = data.get("vector_summaries_by_universe") or {}
            _esu = data.get("event_summaries_by_universe") or {}

            if _vr or _er or _vs or _es or _mc or _univ_raw or _rfr \
                    or _vsu or _esu \
                    or data.get("study_name") is not None:
                from .universe import Universe as _Universe
                from .backtest_run import BacktestRun as _Run
                from .backtest_summary_metrics import BacktestSummaryMetrics as _Sum
                from .backtest_monte_carlo_test import BacktestMonteCarloTest as _MC

                default_study = _Study(
                    name=_study_name,
                    description=_study_desc,
                )

                # Universe
                if _univ_raw:
                    from .universe import Universe as _Universe
                    _univs = [
                        _Universe.from_dict(u) if isinstance(u, dict) else u
                        for u in _univ_raw
                    ]
                    default_study.universe = _univs[0]
                    inst._universe_catalogue = list(_univs)
                if _rfr is not None and default_study.universe is None:
                    default_study.universe = _Universe(risk_free_rate=_rfr)
                elif _rfr is not None and default_study.universe is not None:
                    default_study.universe.risk_free_rate = _rfr

                # Vector slot
                if _vr or _vs or _vsu:
                    v_slot = default_study.get_engine(ENGINE_VECTOR)
                    if _vr:
                        v_slot.runs = [
                            r if not isinstance(r, dict)
                            else _Run.from_dict(r)
                            for r in _vr
                        ]
                    if _vs:
                        v_slot.summary = (
                            _vs if not isinstance(_vs, dict)
                            else _Sum.from_dict(_vs)
                        )
                    if _vsu:
                        v_slot.summaries_by_universe = {
                            k: (_s if not isinstance(_s, dict)
                                else _Sum.from_dict(_s))
                            for k, _s in _vsu.items()
                        }

                # Event slot
                if _er or _es or _esu:
                    e_slot = default_study.get_engine(ENGINE_EVENT)
                    if _er:
                        e_slot.runs = [
                            r if not isinstance(r, dict)
                            else _Run.from_dict(r)
                            for r in _er
                        ]
                    if _es:
                        e_slot.summary = (
                            _es if not isinstance(_es, dict)
                            else _Sum.from_dict(_es)
                        )
                    if _esu:
                        e_slot.summaries_by_universe = {
                            k: (_s if not isinstance(_s, dict)
                                else _Sum.from_dict(_s))
                            for k, _s in _esu.items()
                        }

                # Monte-Carlo tests
                if _mc:
                    from .backtest_monte_carlo_test import BacktestMonteCarloTest as _MC
                    default_study.monte_carlo_tests = [
                        t if not isinstance(t, dict) else _MC.from_dict(t)
                        for t in _mc
                    ]

                inst._studies[_study_name] = default_study

        # Extra studies (from v4/v5 bundle reader)
        for name, study_raw in (data.get("extra_studies") or {}).items():
            if study_raw is None or name in inst._studies:
                continue
            inst._studies[name] = _Study.from_dict(study_raw)

        return inst

    @classmethod
    def open(
        cls,
        directory_path: Union[str, Path],
        backtest_date_ranges: List[BacktestDateRange] = None,
        summary_only: bool = False,
    ) -> 'Backtest':
        """
        Open a backtest report from a directory **or** a ``.iafbt``
        bundle file (issue #487) and return a :class:`Backtest`.

        Args:
            directory_path: Path to the backtest directory or bundle file.
            backtest_date_ranges (List[BacktestDateRange], optional): A list of
                date ranges to filter the backtest runs. If provided, only
                backtest runs matching these date ranges will be loaded.
            summary_only (bool): When True (bundle format v2 only), skip
                eager decoding of heavy time-series blobs (equity curves,
                drawdown series, monthly/yearly returns, etc.). The
                blobs remain in the in-memory dict as
                ``{"@blob": "<key>"}`` references and consumers that
                only need the scalar summary metrics can avoid the
                Parquet decode cost. Ignored for legacy directory
                loaders and v1 bundles, where these series live inline.

        Returns:
            Backtest: An instance of Backtest with the loaded metrics
                and results.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error loading the files.
        """
        path_str = str(directory_path)

        # If the path is a bundle file (or a regular file ending in the
        # bundle extension), load via the bundle reader.
        if os.path.isfile(path_str):
            from .bundle import BUNDLE_EXT, is_bundle_file, open_bundle
            if path_str.endswith(BUNDLE_EXT) or is_bundle_file(path_str):
                bt = open_bundle(path_str, summary_only=summary_only)
                if backtest_date_ranges is not None:
                    _filter_engine_slots_in_place(
                        bt, backtest_date_ranges
                    )
                return bt

        # Fallback: caller passed a path without extension but a sibling
        # bundle file exists (e.g. session_cache stores
        # "<storage>/<algorithm_id>" while the new default save format
        # writes "<storage>/<algorithm_id>.iafbt").
        if not os.path.exists(path_str):
            from .bundle import BUNDLE_EXT, open_bundle
            candidate = path_str + BUNDLE_EXT
            if os.path.isfile(candidate):
                bt = open_bundle(candidate, summary_only=summary_only)
                if backtest_date_ranges is not None:
                    _filter_engine_slots_in_place(
                        bt, backtest_date_ranges
                    )
                return bt

        algorithm_id = None
        vector_runs: List[BacktestRun] = []
        vector_summary: Optional[BacktestSummaryMetrics] = None
        event_runs: List[BacktestRun] = []
        event_summary: Optional[BacktestSummaryMetrics] = None
        monte_carlo_metrics = []
        metadata = {}
        risk_free_rate = None
        parameters = {}

        if not os.path.exists(directory_path):
            raise OperationalException(
                f"The directory {directory_path} does not exist."
            )

        if not os.path.isdir(directory_path):
            raise OperationalException(
                f"Backtest path {directory_path} is not a directory."
            )

        # Load algorithm_id if available
        id_file = os.path.join(directory_path, "algorithm_id.json")

        if os.path.isfile(id_file):
            with open(id_file, 'r') as f:
                try:
                    algorithm_id = json.load(f).get('algorithm_id', None)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding algorithm_id JSON: {e}")
                    algorithm_id = None

        # Load engine slot run lists. v9.0 writes to
        # ``vector_runs/`` / ``event_runs/``; legacy layouts wrote a
        # single ``runs/`` subdirectory which we route into the vector
        # slot per design doc §4.
        def _load_runs_dir(subdir: str) -> List[BacktestRun]:
            runs: List[BacktestRun] = []
            full = os.path.join(directory_path, subdir)
            if not os.path.isdir(full):
                return runs
            for dir_name in os.listdir(full):
                run_path = os.path.join(full, dir_name)
                if not os.path.isdir(run_path):
                    continue
                try:
                    if backtest_date_ranges is not None:
                        temp_run = BacktestRun.open(run_path)
                        match_found = False
                        for date_range in backtest_date_ranges:
                            if (
                                temp_run.backtest_start_date ==
                                date_range.start_date and
                                temp_run.backtest_end_date ==
                                date_range.end_date
                            ):
                                if date_range.name is not None:
                                    if (
                                        temp_run.backtest_date_range_name
                                        == date_range.name
                                    ):
                                        match_found = True
                                        break
                                else:
                                    match_found = True
                                    break
                        if not match_found:
                            continue
                    runs.append(BacktestRun.open(run_path))
                except (OperationalException, json.JSONDecodeError) as e:
                    logger.warning(
                        f"Skipping run at {run_path}: {e}"
                    )
                    continue
            return runs

        vector_runs = _load_runs_dir("vector_runs")
        event_runs = _load_runs_dir("event_runs")

        # Legacy ``runs/`` directory (pre-v9.0) routes into the vector
        # slot. If both shapes coexist we accumulate them — caller
        # shouldn't create that situation but no reason to drop data.
        if os.path.isdir(os.path.join(directory_path, "runs")):
            vector_runs = list(vector_runs) + _load_runs_dir("runs")

        # Load per-engine summaries. Prefer the explicit v9.0 files,
        # fall back to the legacy single ``summary.json`` routed into
        # the vector slot.
        def _load_summary(filename: str):
            full = os.path.join(directory_path, filename)
            if os.path.isfile(full):
                return BacktestSummaryMetrics.open(full)
            return None

        vector_summary = _load_summary("vector_summary.json")
        event_summary = _load_summary("event_summary.json")
        if vector_summary is None:
            vector_summary = _load_summary("summary.json")

        # When no date-range filter is in play we re-derive each
        # engine's summary from the per-run metrics so that on-disk
        # state stays self-consistent regardless of how it was
        # written. The filtered path trusts the persisted summary.
        if backtest_date_ranges is None:
            regen_vector = _regenerate_summary(vector_runs)
            if regen_vector is not None:
                vector_summary = regen_vector
            regen_event = _regenerate_summary(event_runs)
            if regen_event is not None:
                event_summary = regen_event

        # Load backtest Monte-Carlo test metrics
        mc_test_dir = os.path.join(directory_path, "monte_carlo_tests")

        if os.path.isdir(mc_test_dir):
            for dir_name in os.listdir(mc_test_dir):
                mc_test_file = os.path.join(mc_test_dir, dir_name)
                if os.path.isdir(mc_test_file):
                    monte_carlo_metrics.append(
                        BacktestMonteCarloTest.open(mc_test_file)
                    )

        # Load metadata if available
        meta_file = os.path.join(directory_path, "metadata.json")

        if os.path.isfile(meta_file):
            with open(meta_file, 'r') as f:
                metadata = json.load(f)

        # Load risk-free rate if available
        risk_free_rate_file = os.path.join(
            directory_path, "risk_free_rate.json"
        )

        if os.path.isfile(risk_free_rate_file):
            with open(risk_free_rate_file, 'r') as f:
                try:
                    risk_free_rate = json.load(f).get(
                        'risk_free_rate', None
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding risk-free rate JSON: {e}")
                    risk_free_rate = None

        # Load parameters if available
        params_file = os.path.join(directory_path, "parameters.json")

        if os.path.isfile(params_file):
            with open(params_file, 'r') as f:
                try:
                    parameters = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding parameters JSON: {e}")
                    parameters = {}

        # Load tag if available
        tag = None
        tag_file = os.path.join(directory_path, "tag.json")

        if os.path.isfile(tag_file):
            with open(tag_file, 'r') as f:
                try:
                    tag = json.load(f).get('tag', None)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Error decoding tag JSON: {e}"
                    )
                    tag = None

        bt = cls(
            algorithm_id=algorithm_id,
            metadata=metadata,
            parameters=parameters,
            tag=tag,
        )
        if vector_runs or event_runs or monte_carlo_metrics:
            default_study = _Study(name="default")
            if vector_runs:
                slot = default_study.get_engine(ENGINE_VECTOR)
                slot.runs = vector_runs
                slot.summary = vector_summary
            if event_runs:
                slot = default_study.get_engine(ENGINE_EVENT)
                slot.runs = event_runs
                slot.summary = event_summary
            default_study.monte_carlo_tests = monte_carlo_metrics
            bt._studies["default"] = default_study
        return bt

    def save(
        self,
        directory_path: Union[str, Path],
        backtest_date_ranges: List[BacktestDateRange] = None,
    ) -> None:
        """
        Save the backtest metrics to a file in JSON format. The metrics will
        always be saved in a file named `metrics.json`

        Args:
            directory_path (str): The directory where the metrics
                file will be saved.
            backtest_date_ranges (List[BacktestDateRange], optional): A list
                of date ranges to filter the backtest runs. If provided, only
                backtest runs matching these date ranges will be saved.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error saving the files.

        Returns:
            None: This method does not return anything, it saves the
            metrics to a file.
        """
        # Bundle-format dispatch (issue #487):
        #   * If the caller passed a path ending in ``.iafbt``, save as
        #     a bundle file.
        #   * If the caller passed a base path (no extension) and a
        #     sibling ``<path>.iafbt`` exists, replace it in place.
        #   * Otherwise fall through to the legacy directory format
        #     below (preserved for backward compatibility).
        from .bundle import BUNDLE_EXT, save_bundle as _save_bundle
        path_str = str(directory_path)
        if path_str.endswith(BUNDLE_EXT):
            _save_bundle(self, path_str)
            return
        sibling = path_str + BUNDLE_EXT
        if os.path.isfile(sibling):
            _save_bundle(self, sibling)
            return

        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        # Per design doc §4, the legacy directory layout writes per-
        # engine subdirs and per-engine summary files. Apply the
        # caller's date-range filter (if any) per engine slot.
        def _filter(runs: List[BacktestRun]) -> List[BacktestRun]:
            if backtest_date_ranges is None:
                return list(runs)
            return _filter_runs_by_date_ranges(runs, backtest_date_ranges)

        st = self._get_default_study()
        _vr = list(st.get_runs(ENGINE_VECTOR)) if st else []
        _er = list(st.get_runs(ENGINE_EVENT)) if st else []
        engine_slots = (
            (ENGINE_VECTOR, _filter(_vr)),
            (ENGINE_EVENT, _filter(_er)),
        )

        for engine, runs in engine_slots:
            if not runs:
                continue
            run_path = os.path.join(directory_path, f"{engine}_runs")
            os.makedirs(run_path, exist_ok=True)
            for br in runs:
                dir_name = br.create_directory_name()
                destination_run_path = os.path.join(run_path, dir_name)
                os.makedirs(destination_run_path, exist_ok=True)
                br.save(destination_run_path)

        # Always rebuild each engine's summary from its filtered run
        # list so that the on-disk per-engine summary files stay
        # self-consistent with the per-run metrics.json files. See
        # issue #511 (the same invariant carried over to v9.0).
        for engine, runs in engine_slots:
            if not runs:
                continue
            regen = _regenerate_summary(runs)
            if regen is not None and st is not None:
                st.get_engine(engine).summary = regen

        # Write the per-engine summary files.
        for engine, runs in engine_slots:
            summary = self.get_summary(engine)
            if summary is None or not runs:
                continue
            summary_file = os.path.join(
                directory_path, f"{engine}_summary.json"
            )
            summary.save(summary_file)

        _mc_tests = list(st.monte_carlo_tests) if st else []
        if _mc_tests:
            mc_dir_path = os.path.join(
                directory_path, "monte_carlo_tests"
            )
            os.makedirs(mc_dir_path, exist_ok=True)

            for pm in _mc_tests:
                dir_name = pm.create_directory_name()
                pm_path = os.path.join(mc_dir_path, dir_name)
                pm.save(pm_path)

        # Save metadata if available
        if self.metadata:
            meta_file = os.path.join(directory_path, "metadata.json")
            with open(meta_file, 'w') as f:
                json.dump(self.metadata, f, indent=4)

        # Save parameters if available
        if self.parameters:
            params_file = os.path.join(directory_path, "parameters.json")
            with open(params_file, 'w') as f:
                json.dump(self.parameters, f, indent=4)

        # Save strategy IDs if available
        if self.strategy_ids:
            strategy_ids_file = os.path.join(
                directory_path, "strategy_ids.json"
            )
            with open(strategy_ids_file, 'w') as f:
                json.dump({'strategy_ids': self.strategy_ids}, f, indent=4)

        # Save algorithm ID if available
        if self.algorithm_id is not None:
            algorithm_id_file = os.path.join(
                directory_path, "algorithm_id.json"
            )
            with open(algorithm_id_file, 'w') as f:
                json.dump(
                    {'algorithm_id': self.algorithm_id}, f, indent=4
                )

        # Save tag if available
        if self.tag is not None:
            tag_file = os.path.join(directory_path, "tag.json")
            with open(tag_file, 'w') as f:
                json.dump({'tag': self.tag}, f, indent=4)

    def __repr__(self):
        """
        Return a string representation of the Backtest instance.

        Returns:
            str: A string representation of the Backtest instance.
        """
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )

    def save_bundle(
        self,
        path: Union[str, Path],
        *,
        include_ohlcv: bool = False,
        ohlcv_store: Union[str, Path, None] = None,
    ) -> Path:
        """Persist this backtest as a single ``.iafbt`` bundle.

        See :py:func:`investing_algorithm_framework.domain.backtesting.
        bundle.save_bundle` for details. This is a thin convenience
        wrapper.
        """
        from .bundle import save_bundle as _save_bundle
        return _save_bundle(
            self,
            path,
            include_ohlcv=include_ohlcv,
            ohlcv_store=ohlcv_store,
        )

    @staticmethod
    def open_bundle(
        path: Union[str, Path],
        *,
        ohlcv_store: Union[str, Path, None] = None,
    ) -> 'Backtest':
        """Load a :class:`Backtest` from a ``.iafbt`` bundle file."""
        from .bundle import open_bundle as _open_bundle
        return _open_bundle(path, ohlcv_store=ohlcv_store)

    def merge(self, other: 'Backtest') -> 'Backtest':
        """Merge two dual-engine backtests into a new one.

        Runs are concatenated per engine (vector with vector, event
        with event); per-engine summaries are regenerated from the
        full merged run set so they stay self-consistent with the
        per-run metrics (issue #511). ``metadata`` and ``parameters``
        merge with later-wins semantics; ``strategy_ids`` merges as
        an order-preserving union; ``risk_free_rate`` and ``tag``
        prefer ``self`` when present.

        Monte-Carlo tests are simply concatenated (shared across
        engines per design doc §2.3 invariant 3).
        """
        merged = Backtest(algorithm_id=self.algorithm_id)
        self_st = self._get_default_study()
        other_st = other._get_default_study()
        if self_st is not None or other_st is not None:
            target = merged._get_or_create_default_study()
            for engine in ENGINES:
                self_runs = list(self_st.get_runs(engine)) if self_st else []
                other_runs = list(other_st.get_runs(engine)) if other_st else []
                combined = self_runs + other_runs
                if combined:
                    slot = target.get_engine(engine)
                    slot.runs = combined
                    slot.summary = _regenerate_summary(combined)
            self_mcts = list(self_st.monte_carlo_tests) if self_st else []
            other_mcts = list(other_st.monte_carlo_tests) if other_st else []
            target.monte_carlo_tests = self_mcts + other_mcts
        merged.metadata = {**self.metadata, **other.metadata}
        merged.parameters = {**self.parameters, **other.parameters}

        # Order-preserving union for strategy_ids.
        merged.strategy_ids = list(dict.fromkeys(
            list(self.strategy_ids or [])
            + list(other.strategy_ids or [])
        ))

        merged.tag = self.tag if self.tag is not None else other.tag

        if merged.algorithm_id is None:
            merged.algorithm_id = other.algorithm_id

        return merged

    def get_metadata(self) -> Dict[str, str]:
        """
        Get the metadata of the backtest.

        Returns:
            Dict[str, str]: A dictionary containing the metadata
                of the backtest.
        """
        return self.metadata

    def get_backtest_date_ranges(self):
        """
        Get the date ranges for the backtest, across both engines.

        Returns:
            List[BacktestDateRange]: A list of BacktestDateRange objects
                representing the date ranges for each backtest run.
                Vector runs come first, then event runs.
        """
        return [
            BacktestDateRange(
                start_date=run.backtest_start_date,
                end_date=run.backtest_end_date,
                name=run.backtest_date_range_name
            )
            for run in self.get_all_backtest_runs()
        ]

    def add_monte_carlo_test(
        self, monte_carlo_test: BacktestMonteCarloTest
    ) -> None:
        """
        Add a Monte-Carlo test to the backtest.

        Args:
            monte_carlo_test (BacktestMonteCarloTest): The Monte-Carlo test
                to add.
        """
        self._get_or_create_default_study().monte_carlo_tests.append(
            monte_carlo_test
        )

    def __hash__(self):
        if self.algorithm_id is None:
            raise ValueError(
                "Cannot hash Backtest without an algorithm_id value, Please "
                "make sure the Backtest instance has an algorithm_id set."
            )

        meta_id = self.metadata.get("algorithm_id")
        return hash(meta_id)

    def __eq__(self, other):
        if not isinstance(other, Backtest):
            return False

        return self.algorithm_id == other.algorithm_id
