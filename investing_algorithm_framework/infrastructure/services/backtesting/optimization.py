"""Single-writer batch optimization over the public backtest runner."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import errno
import inspect
import json
import logging
import math
from numbers import Integral, Real
import os
from pathlib import Path
from uuid import uuid4

from investing_algorithm_framework.domain import (
    BacktestIndex, OperationalException, generate_algorithm_id,
    generate_backtest_summary_metrics,
)
from investing_algorithm_framework.domain.optimization import (
    CandidateProposal, EvaluationEvidence, OptimizationSearchSpace,
    TrialObservation,
)
from investing_algorithm_framework.domain.backtesting \
    .backtest_summary_metrics import AGGREGATION_SEMANTICS_VERSION
from .vector_resources import MemoryGuard
from .vector_session_index import make_index, persist_index, validated_filter


logger = logging.getLogger("investing_algorithm_framework")
STATE_FILENAME = "optimization_state.json"
EVIDENCE_SCHEMA_VERSION = 1
_UNSUPPORTED = object()


def _json_copy(value):
    """Require portable snapshots; never pickle executable plugin state."""
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def _portable_scalar(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        result = float(value)
        return result if math.isfinite(result) else None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return _UNSUPPORTED


def _callable_identifier(callback):
    if callback is None:
        return None
    return (
        f"{getattr(callback, '__module__', type(callback).__module__)}."
        f"{getattr(callback, '__qualname__', type(callback).__qualname__)}"
    )


def _save_state(path, state):
    payload = json.dumps(state, allow_nan=False, sort_keys=True, indent=2)
    staging = path.with_suffix(".json.pending")
    try:
        with staging.open("w") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
    finally:
        if staging.exists():
            staging.unlink()


@contextmanager
def _search_lock(directory):
    # Advisory OS locks are released on process death, unlike sentinel files.
    with (directory / ".optimization.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)

            def lock():
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def unlock():
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def lock():
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def unlock():
                fcntl.flock(handle, fcntl.LOCK_UN)
        try:
            lock()
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            raise OperationalException(
                f"Optimization directory is already in use: {directory}"
            ) from exc
        try:
            yield
        finally:
            handle.seek(0)
            unlock()


class OptimizationCoordinator:
    """Reuse bounded engine execution; plugins never receive worker pools."""

    def __init__(
        self, runner, configuration, run_configuration, study,
        resource_directory, *, strategies=None, algorithms=None,
        window_filter=None, final_filter=None,
    ):
        if study is None or study.universe is None:
            raise OperationalException(
                "Optimization requires a Study with a universe."
            )
        self.ranges = study.resolve_backtest_date_ranges()
        if not self.ranges:
            raise OperationalException(
                "Optimization requires at least one resolved study window."
            )
        keys = [
            (window.start_date, window.end_date) for window in self.ranges
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Optimization windows must be distinct.")
        self.runner = runner
        self.config = configuration
        self.run_configuration = run_configuration
        self.study = study
        self.window_filter = window_filter
        self.final_filter = final_filter
        self.optimizer = configuration.optimizer
        self.guard = MemoryGuard(
            run_configuration.memory_budget_mb,
            run_configuration.min_available_memory_mb,
        )
        self.guard.require()
        self.candidates = {}
        self.kind = "algorithms" if algorithms is not None else "strategies"
        if configuration.strategy_factory is not None:
            if strategies is not None or algorithms is not None:
                raise ValueError(
                    "Provide either existing candidates or a strategy "
                    "factory and parameters, not both."
                )
            self.space = OptimizationSearchSpace(
                parameters=configuration.parameters,
            )
        else:
            supplied = algorithms if algorithms is not None else strategies
            if supplied is None:
                raise ValueError(
                    "Optimization needs candidates or a strategy factory."
                )
            for candidate in supplied:
                if inspect.isclass(candidate):
                    candidate = candidate()
                algorithm_id = getattr(candidate, "algorithm_id", None)
                if not isinstance(algorithm_id, str) or not algorithm_id:
                    raise ValueError(
                        "Optimization candidates need explicit algorithm IDs."
                    )
                if algorithm_id in self.candidates:
                    raise ValueError(
                        f"Duplicate candidate algorithm ID: {algorithm_id}"
                    )
                self.candidates[algorithm_id] = candidate
            self.space = OptimizationSearchSpace(
                algorithm_ids=tuple(self.candidates),
            )
        if self.space.mode not in self.optimizer.supported_search_spaces:
            raise ValueError(
                f"Optimizer does not support {self.space.mode!r} searches."
            )
        specs = {
            parameter.name: parameter
            for parameter in self.space.parameters
        }
        self.initial_parameters = tuple(
            {
                name: specs[name].resolve(values[name])
                for name in specs
            }
            for values in configuration.initial_parameters
        )
        base = run_configuration.backtest_storage_directory
        if base is None:
            base = Path(resource_directory) / "backtests" / uuid4().hex
        self.directory = (
            Path(base).resolve() / "optimizations" / configuration.search_id
        )
        self.path = self.directory / STATE_FILENAME
        study_config = {
            key: value for key, value in study.to_dict().items()
            if not key.startswith(("vector_", "event_"))
        }
        study_config["engine"] = (
            study.engine.value if study.engine is not None else None
        )
        self.manifest = _json_copy({
            "search_id": configuration.search_id,
            "mode": self.space.mode,
            "candidate_kind": self.kind,
            "algorithm_ids": sorted(self.candidates),
            "parameters": [p.to_dict() for p in configuration.parameters],
            "initial_parameters": [
                dict(values) for values in configuration.initial_parameters
            ],
            "direction": configuration.direction,
            "max_evaluations": configuration.max_evaluations,
            "max_proposals": configuration.max_proposals,
            "proposal_batch_size": configuration.proposal_batch_size,
            "optimizer": (
                f"{type(self.optimizer).__module__}."
                f"{type(self.optimizer).__qualname__}"
            ),
            "objective": _callable_identifier(configuration.objective),
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "summary_metrics_semantics_version":
                AGGREGATION_SEMANTICS_VERSION,
            "window_policy": _callable_identifier(self.window_filter),
            "study": study_config,
            "evaluation": {
                "snapshot_interval": run_configuration.snapshot_interval.value,
                "dynamic_position_sizing": (
                    run_configuration.dynamic_position_sizing
                ),
                "fill_missing_data": run_configuration.fill_missing_data,
            },
        })

    def _snapshot(self):
        state = self.optimizer.state_dict()
        if not isinstance(state, dict):
            raise TypeError("Optimizer state_dict() must return a JSON dict.")
        return _json_copy(state)

    def _load(self):
        if self.path.exists():
            if not self.run_configuration.use_checkpoints:
                raise ValueError(
                    "Search already exists. Enable checkpoints to resume "
                    "or use a new search_id."
                )
            with self.path.open() as handle:
                state = json.load(handle)
            if (
                not isinstance(state, dict) or state.get("version") != 1
                or state.get("manifest") != self.manifest
            ):
                raise ValueError(
                    "Optimization state/context mismatch; use a new "
                    "search_id for a different experiment."
                )
            if (
                state.get("phase") not in {"idle", "evaluate", "tell", "done"}
                or not isinstance(state.get("optimizer_state"), dict)
                or not isinstance(state.get("trials"), list)
                or not isinstance(state.get("evaluations"), dict)
                or not isinstance(state.get("pending"), list)
                or not isinstance(state.get("batch"), int)
            ):
                raise ValueError("Invalid optimization state.")
            self._initialize_optimizer()
            self.optimizer.load_state_dict(
                deepcopy(state["optimizer_state"]),
            )
            return state
        self._initialize_optimizer()
        state = {
            "version": 1, "manifest": self.manifest,
            "phase": "idle", "optimizer_state": self._snapshot(),
            "trials": [], "evaluations": {}, "pending": [], "batch": 0,
            "pruned": [],
        }
        _save_state(self.path, state)
        return state

    def _initialize_optimizer(self):
        self.optimizer.initialize(self.space, self.config.direction)
        if self.config.initial_parameters:
            self.optimizer.set_initial_parameters(deepcopy(
                self.config.initial_parameters,
            ))

    def _resolve(self, proposal):
        if self.space.mode == "finite":
            if proposal.algorithm_id not in self.candidates:
                raise ValueError("Proposal names an unknown algorithm ID.")
            return proposal.algorithm_id, None, None
        if proposal.parameters is None:
            raise ValueError("Parameter search requires parameter proposals.")
        specs = {p.name: p for p in self.config.parameters}
        if set(proposal.parameters) != set(specs):
            raise ValueError("Proposal parameter names must match the space.")
        params = {
            name: spec.resolve(proposal.parameters[name])
            for name, spec in specs.items()
        }
        algorithm_id = generate_algorithm_id(params={
            "length": 32, "search_id": self.config.search_id,
            "parameters": params,
        })
        for constraint in self.config.constraints:
            if not constraint(dict(params)):
                return algorithm_id, params, "Parameter constraint rejected."
        return algorithm_id, params, None

    def _ask(self, state):
        limit = min(
            self.config.proposal_batch_size,
            self.config.max_proposals - len(state["trials"]),
            self.config.max_evaluations - len(state["evaluations"]),
        )
        proposals = list(self.optimizer.ask(limit))
        if not proposals or len(proposals) > limit:
            raise ValueError(
                "Optimizer.ask() must return 1..max_candidates proposals "
                "unless is_finished() is true before asking."
            )
        seen = {trial["proposal_id"] for trial in state["trials"]}
        pending = []
        for proposal in proposals:
            if not isinstance(proposal, CandidateProposal):
                raise TypeError(
                    "Optimizer.ask() must return CandidateProposal."
                )
            if proposal.proposal_id in seen:
                raise ValueError("Optimizer reused a proposal ID.")
            seen.add(proposal.proposal_id)
            algorithm_id, params, error = self._resolve(proposal)
            initial_index = len(state["trials"]) + len(pending)
            if (
                initial_index < len(self.initial_parameters)
                and params != self.initial_parameters[initial_index]
            ):
                raise ValueError(
                    "Optimizer must propose initial_parameters first in "
                    "their configured order."
                )
            trial = {
                "proposal_id": proposal.proposal_id,
                "algorithm_id": algorithm_id, "parameters": params,
                "error": error,
            }
            pending.append(trial)
            if error is None:
                previous = state["evaluations"].get(algorithm_id)
                if previous is not None and previous["parameters"] != params:
                    raise ValueError("Generated algorithm ID collision.")
                if previous is None:
                    state["evaluations"][algorithm_id] = {
                        "parameters": params, "status": "pending",
                        "score": None, "error": None, "evidence": None,
                        "rows": [],
                    }
        state.update(
            pending=pending, phase="evaluate", pruned=[],
            optimizer_state=self._snapshot(),
        )
        _save_state(self.path, state)

    def _candidate(self, algorithm_id, params):
        if self.space.mode == "finite":
            candidate = deepcopy(self.candidates[algorithm_id])
            if self.kind == "algorithms":
                from investing_algorithm_framework.app.algorithm \
                    .algorithm_factory import AlgorithmFactory

                prepared = AlgorithmFactory.create_algorithm(
                    algorithm=candidate,
                )
                existing = {
                    source.get_identifier()
                    for source in candidate.data_sources
                }
                candidate.data_sources.extend(
                    source for source in prepared.data_sources
                    if source.get_identifier() not in existing
                )
            return candidate
        from investing_algorithm_framework.app.strategy import TradingStrategy

        strategy = self.config.strategy_factory(dict(params), algorithm_id)
        if not isinstance(strategy, TradingStrategy):
            raise TypeError("strategy_factory must return a TradingStrategy.")
        if strategy.algorithm_id != algorithm_id:
            raise ValueError(
                "strategy_factory must preserve the supplied algorithm_id."
            )
        return strategy

    @staticmethod
    def _window_key(date_range):
        return (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )

    def _window_descriptor(self, date_range, execution_order):
        part = self.study.window_part
        if hasattr(part, "value"):
            part = part.value
        return {
            "key": self._window_key(date_range),
            "name": date_range.name,
            "start": date_range.start_date.isoformat(),
            "end": date_range.end_date.isoformat(),
            "window_part": part,
            "execution_order": execution_order,
        }

    def _evaluation_evidence(
        self, algorithm_id, parameters, index, *,
        completed_ranges=None, stop_reason=None,
    ):
        engine_type = None
        if not index.df.empty:
            engine_type = str(index.df["engine_type"].iloc[0])
        elif self.study.engine is not None:
            engine_type = self.study.engine.value
            if engine_type == "event_driven":
                engine_type = "event"
        if engine_type is None:
            raise ValueError("Optimization evidence requires an engine.")

        order_by_range = {
            (date_range.start_date, date_range.end_date): position
            for position, date_range in enumerate(self.ranges)
        }
        backtest = None
        slot = None
        runs = []
        try:
            backtest = next(index.iter_backtests())
        except StopIteration:
            pass
        if backtest is not None:
            completed_study = backtest.get_study(self.study.name)
            if completed_study is not None:
                slot = completed_study.engine_results.get(engine_type)
                if slot is not None:
                    runs = list(slot.runs or [])

        if completed_ranges is None:
            completed_pairs = {
                (run.backtest_start_date, run.backtest_end_date)
                for run in runs
                if (
                    run.backtest_start_date, run.backtest_end_date
                ) in order_by_range
            }
            completed_ranges = [
                date_range for date_range in self.ranges
                if (date_range.start_date, date_range.end_date)
                in completed_pairs
            ]
        completed_pairs = {
            (date_range.start_date, date_range.end_date)
            for date_range in completed_ranges
        }
        runs = [
            run for run in runs
            if (run.backtest_start_date, run.backtest_end_date)
            in completed_pairs
        ]

        run_metrics = []
        for run in sorted(
            runs,
            key=lambda run: order_by_range[
                (run.backtest_start_date, run.backtest_end_date)
            ],
        ):
            metrics = {}
            if run.backtest_metrics is not None:
                for name, value in run.backtest_metrics.to_dict(
                    materialize_history=False,
                ).items():
                    scalar = _portable_scalar(value)
                    if scalar is not _UNSUPPORTED:
                        metrics[name] = scalar
            metadata = run.metadata or {}
            universe_key = _portable_scalar(metadata.get("universe_key"))
            if universe_key is _UNSUPPORTED:
                universe_key = None
            pair = (run.backtest_start_date, run.backtest_end_date)
            run_metrics.append({
                "window_key": self._window_key(
                    self.ranges[order_by_range[pair]]
                ),
                "execution_order": order_by_range[pair],
                "start": run.backtest_start_date.isoformat(),
                "end": run.backtest_end_date.isoformat(),
                "window_part": run.window_role,
                "universe_key": universe_key,
                "metrics": metrics,
            })

        summaries = []
        summary_by_universe = {}
        if slot is not None:
            slot.runs = runs
            slot.summary = generate_backtest_summary_metrics([
                run.backtest_metrics for run in runs
                if run.backtest_metrics is not None
            ], expected_window_count=len(self.ranges))
            backtest.regenerate_summaries_by_universe()
            summary_by_universe = {
                None: slot.summary,
                **(slot.summaries_by_universe or {}),
            }
        for universe_key, summary in summary_by_universe.items():
            if summary is None:
                continue
            metrics = {}
            for name, value in summary.to_dict().items():
                scalar = _portable_scalar(value)
                if scalar is not _UNSUPPORTED:
                    metrics[name] = scalar
            if metrics:
                summaries.append({
                    "universe_key": universe_key,
                    "metrics": metrics,
                })

        descriptors = tuple(
            self._window_descriptor(date_range, order_by_range[
                (date_range.start_date, date_range.end_date)
            ])
            for date_range in completed_ranges
        )
        return EvaluationEvidence(
            evaluation_id=f"{self.config.search_id}:{algorithm_id}",
            algorithm_id=algorithm_id,
            parameters=parameters or {},
            study_name=self.study.name,
            engine_type=engine_type,
            completed_window_keys=[
                descriptor["key"] for descriptor in descriptors
            ],
            completed_windows=descriptors,
            required_windows=len(self.ranges),
            run_metrics=run_metrics,
            summary_metrics=summaries,
            stop_reason=stop_reason,
            policy_identifier=(
                _callable_identifier(self.window_filter)
                if stop_reason == "window_filter_pruned" else None
            ),
        )

    def _evaluate(self, state):
        needed = {
            trial["algorithm_id"] for trial in state["pending"]
            if trial["error"] is None and
            state["evaluations"][trial["algorithm_id"]]["status"] == "pending"
        }
        batch_directory = self.directory / "batches" / str(state["batch"])

        def filter_window(index, date_range):
            filtered = validated_filter(index, self.window_filter, date_range)
            pruned = set(index.df["algorithm_id"]) - set(
                filtered.df["algorithm_id"]
            )
            current_position = next(
                position for position, configured in enumerate(self.ranges)
                if (
                    configured.start_date, configured.end_date
                ) == (date_range.start_date, date_range.end_date)
            )
            completed_ranges = self.ranges[:current_position + 1]
            for algorithm_id in sorted(pruned):
                evaluation = state["evaluations"][algorithm_id]
                candidate_index = index.filter(
                    lambda row, key=algorithm_id:
                    row["algorithm_id"] == key
                )
                evidence = self._evaluation_evidence(
                    algorithm_id, evaluation["parameters"],
                    candidate_index, completed_ranges=completed_ranges,
                    stop_reason="window_filter_pruned",
                )
                evaluation["evidence"] = evidence.to_dict()
            state["pruned"] = sorted(set(state["pruned"]) | pruned)
            _save_state(self.path, state)
            return filtered

        if needed:
            candidates = [
                self._candidate(key, state["evaluations"][key]["parameters"])
                for key in sorted(needed)
            ]
            self.guard.require()
            index = self.runner(
                **{self.kind: candidates},
                study=deepcopy(self.study),
                run_configuration=replace(
                    self.run_configuration,
                    backtest_storage_directory=batch_directory,
                ),
                window_metrics_filter_function=(
                    filter_window if self.window_filter is not None else None
                ),
            )
            del candidates
            self.guard.require()
            if not isinstance(index, BacktestIndex):
                raise TypeError("Backtest runner must return a BacktestIndex.")
            for algorithm_id in sorted(needed):
                evaluation = state["evaluations"][algorithm_id]
                candidate_index = index.filter(
                    lambda row: row["algorithm_id"] == algorithm_id
                )
                if algorithm_id in state["pruned"]:
                    evaluation.update(
                        status="pruned",
                        error="Window filter pruned candidate.",
                    )
                elif not self._complete(candidate_index):
                    evidence = self._evaluation_evidence(
                        algorithm_id, evaluation["parameters"],
                        candidate_index,
                        stop_reason="incomplete_evaluation",
                    )
                    evaluation.update(
                        status="failed",
                        error="Candidate did not complete every study window.",
                        evidence=evidence.to_dict(),
                    )
                    logger.warning(
                        "Optimization candidate %s did not complete all "
                        "windows; no objective score assigned.", algorithm_id,
                    )
                else:
                    score = self.config.objective(BacktestIndex(
                        candidate_index.directory,
                        candidate_index.df.copy(deep=True),
                    ))
                    observation = TrialObservation(
                        proposal_id="validation", algorithm_id=algorithm_id,
                        status="complete", score=score,
                    )
                    rows = json.loads(candidate_index.df.to_json(
                        orient="records", double_precision=15,
                    ))
                    for row in rows:
                        row["bundle_path"] = os.path.relpath(
                            candidate_index.directory / row["bundle_path"],
                            self.directory,
                        )
                    evidence = self._evaluation_evidence(
                        algorithm_id, evaluation["parameters"],
                        candidate_index, completed_ranges=self.ranges,
                    )
                    evaluation.update(
                        status="complete", score=float(observation.score),
                        evidence=evidence.to_dict(), rows=rows,
                    )
                self.guard.require()
        observations = []
        for trial in state["pending"]:
            if trial["error"] is not None:
                observation = TrialObservation(
                    **trial, status="invalid",
                )
            else:
                evaluation = state["evaluations"][trial["algorithm_id"]]
                observation = TrialObservation(
                    proposal_id=trial["proposal_id"],
                    algorithm_id=trial["algorithm_id"],
                    parameters=trial["parameters"],
                    status=evaluation["status"], score=evaluation["score"],
                    error=evaluation["error"],
                    evidence=(
                        EvaluationEvidence.from_dict(evaluation["evidence"])
                        if evaluation.get("evidence") is not None else None
                    ),
                )
            observations.append(observation.to_dict())
        state.update(phase="tell", observations=observations)
        _save_state(self.path, state)

    def _complete(self, index):
        frame = index.df
        if frame.empty or "summary.number_of_windows" not in frame:
            return False
        pooled = frame.loc[frame["universe_key"].isna()]
        return (
            len(pooled) == 1
            and pooled["summary.number_of_windows"].iloc[0] == len(self.ranges)
        )

    def _tell(self, state):
        observations = [
            TrialObservation.from_dict(item) for item in state["observations"]
        ]
        self.optimizer.tell(observations)
        self.guard.require()
        # The snapshot and applied observations advance in one atomic write.
        # A crash before it restores pre-tell state and replays the batch.
        state["optimizer_state"] = self._snapshot()
        state["trials"].extend(state.pop("observations"))
        state.update(phase="idle", pending=[], batch=state["batch"] + 1)
        _save_state(self.path, state)

    def run(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with _search_lock(self.directory):
            state = self._load()
            while state["phase"] != "done":
                self.guard.require()
                if state["phase"] == "idle":
                    initial_parameters_remain = (
                        len(state["trials"]) < len(self.initial_parameters)
                    )
                    if (
                        (
                            not initial_parameters_remain
                            and self.optimizer.is_finished()
                        )
                        or len(state["evaluations"]) >=
                        self.config.max_evaluations
                        or len(state["trials"]) >= self.config.max_proposals
                    ):
                        state["phase"] = "done"
                        _save_state(self.path, state)
                        break
                    self._ask(state)
                if state["phase"] == "evaluate":
                    self._evaluate(state)
                if state["phase"] == "tell":
                    self._tell(state)
            rows = [
                row for key in sorted(state["evaluations"])
                for evaluation in [state["evaluations"][key]]
                if evaluation["status"] == "complete"
                for row in evaluation["rows"]
            ]
            for row in rows:
                path = self.directory / row["bundle_path"]
                if not path.is_file():
                    raise FileNotFoundError(
                        f"Completed optimization artifact is missing: {path}"
                    )
            index = make_index(self.directory, _json_copy(rows))
            if self.final_filter is not None:
                index = validated_filter(index, self.final_filter)
            self.guard.require()
            persist_index(index)
            logger.info("Optimization results: %s", self.directory)
            return index
