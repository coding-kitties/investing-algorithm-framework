from __future__ import annotations

import json
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from numbers import Integral, Real
from typing import TYPE_CHECKING, Callable, Literal, Optional, Union

if TYPE_CHECKING:
    from investing_algorithm_framework.app.strategy import TradingStrategy
    from investing_algorithm_framework.domain.backtesting.backtest_utils \
        import BacktestIndex


Number = Union[int, float]


def _validate_name(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _number(value: Real, name: str, finite: bool = True) -> Number:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a real number")
    if isinstance(value, Integral):
        return int(value)
    result = float(value)
    if finite and not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _float(value: Real, name: str) -> float:
    try:
        result = float(_number(value, name))
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _snap_to_grid(
    raw: Number, lower: Number, upper: Number, step: Number,
) -> Fraction:
    # Decimal fractions avoid off-by-one grid endpoints and float overflow.
    value = Fraction(str(min(upper, max(lower, raw))))
    start = Fraction(str(lower))
    increment = Fraction(str(step))
    last = (Fraction(str(upper)) - start) // increment
    index = min(last, max(0, round((value - start) / increment)))
    return start + index * increment


@dataclass(frozen=True)
class IntegerParameter:
    """An inclusive integer range, snapped to its lower-anchored grid."""

    name: str
    lower: int
    upper: int
    step: int = 1

    def __post_init__(self) -> None:
        _validate_name(self.name, "name")
        for name in ("lower", "upper", "step"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError(f"{name} must be an integer")
            object.__setattr__(self, name, int(value))
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")
        if self.step <= 0:
            raise ValueError("step must be a positive integer")

    def resolve(self, raw: float) -> int:
        """Clamp then snap to the nearest grid point (ties to even index)."""
        value = _number(raw, self.name)
        return int(_snap_to_grid(
            value, self.lower, self.upper, self.step,
        ))

    def to_dict(self) -> dict:
        return {
            "type": "integer", "name": self.name,
            "lower": self.lower, "upper": self.upper, "step": self.step,
        }


@dataclass(frozen=True)
class FloatParameter:
    """An inclusive float range; a zero step makes it continuous."""

    name: str
    lower: float
    upper: float
    step: float = 0

    def __post_init__(self) -> None:
        _validate_name(self.name, "name")
        for name in ("lower", "upper", "step"):
            object.__setattr__(self, name, _float(getattr(self, name), name))
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")
        if self.step < 0:
            raise ValueError("step must be nonnegative")

    def resolve(self, raw: float) -> float:
        """Clamp then snap to the nearest grid point (ties to even index)."""
        value = _number(raw, self.name)
        if self.step == 0:
            return float(min(self.upper, max(self.lower, value)))
        return float(_snap_to_grid(
            value, self.lower, self.upper, self.step,
        ))

    def to_dict(self) -> dict:
        return {
            "type": "float", "name": self.name,
            "lower": self.lower, "upper": self.upper, "step": self.step,
        }


Parameter = Union[IntegerParameter, FloatParameter]


def _parameters(parameters: Sequence[Parameter]) -> tuple[Parameter, ...]:
    if isinstance(parameters, (str, bytes)) \
            or not isinstance(parameters, Sequence):
        raise ValueError("parameters must be a sequence of parameters")
    result = tuple(parameters)
    if any(not isinstance(p, (IntegerParameter, FloatParameter))
           for p in result):
        raise ValueError("parameters must contain parameter definitions")
    if len({p.name for p in result}) != len(result):
        raise ValueError("parameter names must be unique")
    return result


def _parameter_values(
    parameters: Mapping[str, Number], finite: bool,
) -> dict[str, Number]:
    if not isinstance(parameters, Mapping):
        raise ValueError("parameters must be a named numeric mapping")
    result = {}
    for name, value in parameters.items():
        _validate_name(name, "parameter name")
        result[name] = _number(value, name, finite=finite)
    return result


@dataclass(frozen=True)
class CandidateProposal:
    """A raw named-parameter proposal or a finite candidate identifier."""

    proposal_id: str
    parameters: Optional[Mapping[str, float]] = None
    algorithm_id: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_name(self.proposal_id, "proposal_id")
        if (self.parameters is None) == (self.algorithm_id is None):
            raise ValueError("provide exactly one of parameters/algorithm_id")
        if self.algorithm_id is not None:
            _validate_name(self.algorithm_id, "algorithm_id")
        if self.parameters is not None:
            # Resolution, not proposal construction, rejects nonfinite values.
            object.__setattr__(self, "parameters", _parameter_values(
                self.parameters, finite=False,
            ))


def _json_data(value, name: str):
    try:
        return json.loads(json.dumps(
            value, allow_nan=False, sort_keys=True,
        ))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain JSON-safe values") from exc


def _json_mappings(values, name: str) -> tuple[dict, ...]:
    if isinstance(values, (str, bytes)) \
            or not isinstance(values, Sequence) \
            or any(not isinstance(value, Mapping) for value in values):
        raise ValueError(f"{name} must be a sequence of mappings")
    return tuple(
        _json_data(dict(value), name) for value in values
    )


@dataclass(frozen=True)
class EvaluationEvidence:
    """Versioned terminal evidence for one distinct candidate evaluation."""

    evaluation_id: str
    algorithm_id: str
    parameters: Mapping[str, Number]
    study_name: str
    engine_type: str
    completed_window_keys: Sequence[str]
    completed_windows: Sequence[Mapping]
    required_windows: int
    run_metrics: Sequence[Mapping]
    summary_metrics: Sequence[Mapping]
    stop_reason: Optional[str] = None
    policy_identifier: Optional[str] = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in (
            "evaluation_id", "algorithm_id", "study_name", "engine_type",
        ):
            _validate_name(getattr(self, name), name)
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise ValueError("unsupported evidence schema_version")
        if isinstance(self.required_windows, bool) \
                or not isinstance(self.required_windows, int) \
                or self.required_windows < 0:
            raise ValueError("required_windows must be a nonnegative integer")
        if isinstance(self.completed_window_keys, (str, bytes)) \
                or not isinstance(self.completed_window_keys, Sequence):
            raise ValueError(
                "completed_window_keys must be a sequence of strings"
            )
        keys = tuple(self.completed_window_keys)
        if any(not isinstance(key, str) or not key for key in keys):
            raise ValueError(
                "completed_window_keys must contain nonempty strings"
            )
        if len(set(keys)) != len(keys):
            raise ValueError("completed_window_keys must be unique")
        windows = _json_mappings(
            self.completed_windows, "completed_windows",
        )
        if len(keys) != len(windows):
            raise ValueError(
                "completed window keys and descriptors must have equal length"
            )
        if len(windows) > self.required_windows:
            raise ValueError(
                "completed windows cannot exceed required_windows"
            )
        object.__setattr__(
            self, "parameters",
            _parameter_values(self.parameters, finite=True),
        )
        object.__setattr__(self, "completed_window_keys", keys)
        object.__setattr__(self, "completed_windows", windows)
        object.__setattr__(
            self, "run_metrics",
            _json_mappings(self.run_metrics, "run_metrics"),
        )
        object.__setattr__(
            self, "summary_metrics",
            _json_mappings(self.summary_metrics, "summary_metrics"),
        )
        for name in ("stop_reason", "policy_identifier"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value
            ):
                raise ValueError(f"{name} must be a nonempty string or None")

    @property
    def consumed_windows(self) -> int:
        return len(self.completed_windows)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "algorithm_id": self.algorithm_id,
            "parameters": dict(self.parameters),
            "study_name": self.study_name,
            "engine_type": self.engine_type,
            "completed_window_keys": list(self.completed_window_keys),
            "completed_windows": list(self.completed_windows),
            "required_windows": self.required_windows,
            "consumed_windows": self.consumed_windows,
            "run_metrics": list(self.run_metrics),
            "summary_metrics": list(self.summary_metrics),
            "stop_reason": self.stop_reason,
            "policy_identifier": self.policy_identifier,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EvaluationEvidence:
        values = dict(data)
        consumed = values.pop("consumed_windows", None)
        evidence = cls(**values)
        if consumed is not None and consumed != evidence.consumed_windows:
            raise ValueError("consumed_windows does not match evidence")
        return evidence


@dataclass(frozen=True)
class TrialObservation:
    """Serializable feedback; only completed trials carry a finite score."""

    proposal_id: str
    algorithm_id: Optional[str]
    status: Literal["complete", "invalid", "failed", "pruned"]
    score: Optional[float] = None
    parameters: Optional[Mapping[str, Number]] = None
    error: Optional[str] = None
    evidence: Optional[EvaluationEvidence] = None

    def __post_init__(self) -> None:
        _validate_name(self.proposal_id, "proposal_id")
        if self.algorithm_id is not None:
            _validate_name(self.algorithm_id, "algorithm_id")
        if self.status not in ("complete", "invalid", "failed", "pruned"):
            raise ValueError(
                "status must be complete, invalid, failed or pruned"
            )
        if self.status == "complete":
            object.__setattr__(self, "score", _float(self.score, "score"))
        elif self.score is not None:
            raise ValueError("only complete trials may have a score")
        if self.parameters is not None:
            object.__setattr__(self, "parameters", _parameter_values(
                self.parameters, finite=True,
            ))
        if self.error is not None and not isinstance(self.error, str):
            raise ValueError("error must be a string or None")
        if self.evidence is not None \
                and not isinstance(self.evidence, EvaluationEvidence):
            raise ValueError("evidence must be EvaluationEvidence or None")
        if self.evidence is not None:
            if self.algorithm_id != self.evidence.algorithm_id:
                raise ValueError(
                    "observation and evidence algorithm IDs must match"
                )
            if self.parameters is not None \
                    and dict(self.parameters) != dict(
                        self.evidence.parameters
                    ):
                raise ValueError(
                    "observation and evidence parameters must match"
                )

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "algorithm_id": self.algorithm_id,
            "status": self.status,
            "score": self.score,
            "parameters": (
                dict(self.parameters) if self.parameters is not None else None
            ),
            "error": self.error,
            "evidence": (
                self.evidence.to_dict()
                if self.evidence is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrialObservation:
        values = dict(data)
        evidence = values.get("evidence")
        if evidence is not None:
            values["evidence"] = EvaluationEvidence.from_dict(evidence)
        return cls(**values)


@dataclass(frozen=True)
class OptimizationSearchSpace:
    """Exactly one nonempty source: parameter definitions or algorithm IDs."""

    parameters: Sequence[Parameter] = ()
    algorithm_ids: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _parameters(self.parameters))
        if isinstance(self.algorithm_ids, (str, bytes)) \
                or not isinstance(self.algorithm_ids, Sequence):
            raise ValueError("algorithm_ids must be a sequence of strings")
        ids = tuple(self.algorithm_ids)
        for algorithm_id in ids:
            _validate_name(algorithm_id, "algorithm_id")
        if len(set(ids)) != len(ids):
            raise ValueError("algorithm_ids must be unique")
        object.__setattr__(self, "algorithm_ids", ids)
        if bool(self.parameters) == bool(ids):
            raise ValueError("provide exactly one nonempty search space")

    @property
    def mode(self) -> Literal["parameters", "finite"]:
        return "parameters" if self.parameters else "finite"


class StrategyOptimizer(ABC):
    """User-implemented ask/tell search policy; no backtest execution."""

    supported_search_spaces = frozenset()

    def set_initial_parameters(
        self, initial_parameters: Sequence[Mapping[str, Number]],
    ) -> None:
        """Queue configured parameter points ahead of ordinary proposals."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support "
            f"{len(initial_parameters)} initial parameter points"
        )

    @abstractmethod
    def initialize(
        self, search_space: OptimizationSearchSpace, direction: str,
    ) -> None:
        pass

    @abstractmethod
    def ask(self, max_candidates: int) -> Sequence[CandidateProposal]:
        pass

    @abstractmethod
    def tell(self, observations: Sequence[TrialObservation]) -> None:
        pass

    @abstractmethod
    def is_finished(self) -> bool:
        pass

    @abstractmethod
    def state_dict(self) -> dict:
        pass

    @abstractmethod
    def load_state_dict(self, state: dict) -> None:
        pass


@dataclass(frozen=True)
class OptimizationConfiguration:
    """Search policy and budgets, independent of backtest run settings."""

    search_id: str
    optimizer: StrategyOptimizer
    objective: Callable[[BacktestIndex], float]
    strategy_factory: Optional[Callable[[dict, str], TradingStrategy]] = None
    parameters: Sequence[Parameter] = ()
    initial_parameters: Sequence[Mapping[str, Number]] = ()
    constraints: Sequence[Callable[[dict], bool]] = ()
    direction: str = "maximize"
    max_evaluations: int = 100
    max_proposals: int = 1000
    proposal_batch_size: int = 16

    def __post_init__(self) -> None:
        if not isinstance(self.search_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.search_id,
        ) or self.search_id.endswith("."):
            raise ValueError("search_id must be a safe filesystem name")
        if not isinstance(self.optimizer, StrategyOptimizer):
            raise ValueError("optimizer must be a StrategyOptimizer")
        modes = self.optimizer.supported_search_spaces
        if not isinstance(modes, (set, frozenset, tuple, list)) \
                or not modes or any(
                    mode not in ("finite", "parameters") for mode in modes
                ):
            raise ValueError(
                "optimizer must declare nonempty supported_search_spaces "
                "containing only finite and/or parameters"
            )
        if not callable(self.objective):
            raise ValueError("objective must be callable")
        if self.strategy_factory is not None \
                and not callable(self.strategy_factory):
            raise ValueError("strategy_factory must be callable")
        object.__setattr__(self, "parameters", _parameters(self.parameters))
        if (self.strategy_factory is not None) != bool(self.parameters):
            raise ValueError(
                "strategy_factory and parameters must be provided together"
            )
        if isinstance(self.initial_parameters, (str, bytes)) \
                or not isinstance(self.initial_parameters, Sequence):
            raise ValueError(
                "initial_parameters must be a sequence of parameter mappings"
            )
        initial_parameters = tuple(
            _parameter_values(values, finite=True)
            for values in self.initial_parameters
        )
        if initial_parameters and self.strategy_factory is None:
            raise ValueError(
                "initial_parameters require generated parameters"
            )
        expected_names = {parameter.name for parameter in self.parameters}
        if any(set(values) != expected_names for values in initial_parameters):
            raise ValueError(
                "initial parameter names must match the parameter space"
            )
        if initial_parameters and (
            type(self.optimizer).set_initial_parameters
            is StrategyOptimizer.set_initial_parameters
        ):
            raise ValueError(
                f"{type(self.optimizer).__name__} does not support "
                "initial_parameters"
            )
        object.__setattr__(
            self, "initial_parameters",
            tuple(dict(values) for values in initial_parameters),
        )
        if isinstance(self.constraints, (str, bytes)) \
                or not isinstance(self.constraints, Sequence) \
                or any(not callable(c) for c in self.constraints):
            raise ValueError("constraints must be a sequence of callables")
        object.__setattr__(self, "constraints", tuple(self.constraints))
        if self.constraints and self.strategy_factory is None:
            raise ValueError("constraints require generated parameters")
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction must be maximize or minimize")
        for name in (
            "max_evaluations", "max_proposals", "proposal_batch_size",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) \
                    or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if len(initial_parameters) > self.max_evaluations:
            raise ValueError(
                "initial_parameters cannot exceed max_evaluations"
            )
        if len(initial_parameters) > self.max_proposals:
            raise ValueError(
                "initial_parameters cannot exceed max_proposals"
            )
