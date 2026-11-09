"""Native-timeframe indicator declarations and bindings to confluence cards."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import Callable, Literal, Mapping

from .models.confluence import (
    AllOf, AnyOf, AtLeast, ConditionExpression, Expression, Not, Operator,
    Requirement, Veto, condition,
)
from .models.confluence_score import (
    ConfluenceScoreCard, ConfluenceScoreRule, Rule, Threshold,
)
from .models.data.data_source import DataSource
from .models.signal import SignalSide
from .models.time_frame import TimeFrame
from .utils.immutable import reduce_immutable_dataclass


OUTPUTS = {
    "z_score": ("value",), "willr": ("value",), "rsi": ("value",),
    "wilders_rsi": ("value",), "ema": ("value",),
    "macd": ("macd", "signal", "histogram"), "stochastic": ("k", "d"),
}


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_match_expression(expression, names):
    if isinstance(expression, (Rule, Threshold)):
        return  # The compiled card validates these references.
    if isinstance(expression, ConditionExpression):
        predicate = expression.condition
        references = {predicate.indicator}
        if predicate.reference is not None:
            references.add(predicate.reference)
        if predicate.timeframe is not None or references - names:
            raise ValueError("Card gates must reference named indicator-rule matches")
        if predicate.operator in (Operator.CROSS_ABOVE, Operator.CROSS_BELOW):
            raise ValueError("Card gates cannot cross rule matches; declare native lookbacks instead")
    elif isinstance(expression, (AllOf, AnyOf, AtLeast)):
        for child in expression.expressions:
            _validate_match_expression(child, names)
    elif isinstance(expression, Not):
        _validate_match_expression(expression.expression, names)
    else:
        raise ValueError("Card match conditions must use built-in condition expressions")


@dataclass(frozen=True)
class IndicatorConfig:
    id: str
    indicator: str | None = None
    period: int = 14
    timeframe: str | None = None
    data_source: str | DataSource | Mapping[str, str] | None = None
    scale: float = 1
    k_slowing: int = 3
    d_period: int = 3
    short_period: int = 12
    long_period: int = 26
    signal_period: int = 9
    symbol: str | None = None
    calculate: Callable | None = None
    parameters: Mapping = field(default_factory=dict)
    output_columns: list[str] | tuple[str, ...] | None = None
    minimum_history: int = 1
    history: str = "continuous"
    execution: str = "per_decision"
    data_sources: (
        list[str | DataSource] | tuple[str | DataSource, ...] | None
    ) = field(default=None, kw_only=True)

    def __reduce__(self):
        return reduce_immutable_dataclass(self)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Indicator id must be non-empty")
        if self.calculate is not None or self.indicator is None:
            if not callable(self.calculate):
                raise TypeError("calculate must be callable")
            if self.indicator is not None:
                raise ValueError("Declare either indicator or calculate, not both")
            if not isinstance(self.parameters, Mapping):
                raise TypeError("parameters must be a mapping")
            columns = self.output_columns
            if (not isinstance(columns, (list, tuple)) or not columns
                    or any(not isinstance(name, str) or not name.strip() for name in columns)
                    or len(set(columns)) != len(columns)):
                raise ValueError("output_columns must contain unique non-empty column names")
            object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
            object.__setattr__(self, "output_columns", tuple(columns))
        elif self.indicator not in OUTPUTS:
            raise ValueError(f"Unsupported indicator: {self.indicator}")
        if self.history != "continuous":
            raise ValueError("history must be continuous")
        if self.execution not in ("per_decision", "precompute"):
            raise ValueError("execution must be per_decision or precompute")
        _positive_int(self.minimum_history, "minimum_history")
        if self.timeframe is not None or self.calculate is None:
            timeframe = TimeFrame.from_value(self.timeframe or "2h")
            if timeframe is TimeFrame.CURRENT:
                raise ValueError("Indicators require a native candle timeframe")
            object.__setattr__(self, "timeframe", timeframe.value)
        for name in ("period", "k_slowing", "d_period", "short_period",
                     "long_period", "signal_period"):
            _positive_int(getattr(self, name), name)
        _finite(self.scale, "scale")
        if self.indicator == "z_score" and self.period < 2:
            raise ValueError("z_score period must be at least 2")
        if self.indicator == "macd" and self.short_period >= self.long_period:
            raise ValueError("MACD short_period must be less than long_period")
        source = self.data_source
        if isinstance(source, Mapping):
            if not source or any(
                not isinstance(symbol, str) or not symbol
                or symbol != symbol.strip().upper()
                or not isinstance(identifier, str) or not identifier
                or identifier != identifier.strip()
                for symbol, identifier in source.items()
            ):
                raise ValueError("data_source mappings require uppercase symbols and non-empty identifiers")
            object.__setattr__(self, "data_source", MappingProxyType(dict(source)))
        elif source is not None:
            if not isinstance(source, (str, DataSource)):
                raise TypeError("data_source must be an identifier, DataSource, or symbol mapping")
            if isinstance(source, str) and (not source or source != source.strip()):
                raise ValueError("data_source must be a non-empty source identifier")
        if self.data_sources is not None:
            if source is not None:
                raise ValueError(
                    "Specify either data_source or data_sources, not both"
                )
            if (not isinstance(self.data_sources, (list, tuple))
                    or not self.data_sources
                    or any(not isinstance(item, (str, DataSource))
                           for item in self.data_sources)):
                raise ValueError(
                    "data_sources must be a non-empty list or tuple of "
                    "source identifiers or DataSource objects"
                )
            identifiers = self.source_identifiers
            if (any(not isinstance(item, str) or not item
                    or item != item.strip() for item in identifiers)
                    or len(set(identifiers)) != len(identifiers)):
                raise ValueError(
                    "data_sources must contain unique non-empty identifiers"
                )
            object.__setattr__(self, "data_sources", identifiers)

    @property
    def source_identifiers(self) -> tuple[str, ...] | None:
        if self.data_sources is None:
            return None
        return tuple(
            source.get_identifier() if isinstance(source, DataSource)
            else source for source in self.data_sources
        )

    def to_dict(self):
        """Export built-in declarations without serializing executable callables."""
        if self.calculate is not None:
            raise TypeError("Callable indicators must be reconstructed from their Python declarations")
        source = self.data_source
        if isinstance(source, DataSource):
            source = source.get_identifier()
        elif isinstance(source, Mapping):
            source = dict(source)
        definition = {
            "id": self.id, "indicator": self.indicator, "period": self.period,
            "timeframe": self.timeframe, "data_source": source, "scale": self.scale,
            "k_slowing": self.k_slowing, "d_period": self.d_period,
            "short_period": self.short_period, "long_period": self.long_period,
            "signal_period": self.signal_period, "symbol": self.symbol,
            "minimum_history": self.minimum_history, "history": self.history,
            "execution": self.execution,
        }
        if self.data_sources is not None:
            definition["data_sources"] = list(self.source_identifiers)
        return definition

    @classmethod
    def from_dict(cls, value):
        return cls(**value)

    def required_window(self, output=None):
        """Minimum contiguous observations for a finite selected output."""
        if self.calculate is not None:
            return self.minimum_history
        if self.indicator in ("rsi", "wilders_rsi"):
            return self.period + 1
        if self.indicator == "stochastic":
            return self.period + self.k_slowing - 1 + (
                self.d_period - 1 if output in (None, "d") else 0
            )
        if self.indicator == "macd":
            return self.long_period + (
                self.signal_period - 1 if output in (None, "signal", "histogram") else 0
            )
        return self.period

    @property
    def outputs(self):
        return self.output_columns if self.calculate is not None else OUTPUTS[self.indicator]


@dataclass(frozen=True)
class IndicatorRule:
    indicator_id: str
    threshold: float
    group_weights: Mapping[str, float] | None = None
    lookback_period: int = 1
    comparison: str = "le"
    output: str | None = None
    output_column: str | None = None
    lookback_scope: Literal["market", "position"] = "market"
    lower_bound: float | None = None
    upper_bound: float | None = None
    initial_delay: int = 0
    initial_delay_mode: Literal["continuous", "recheck"] = "continuous"

    def __reduce__(self):
        return reduce_immutable_dataclass(self)

    def __post_init__(self):
        if not isinstance(self.indicator_id, str) or not self.indicator_id:
            raise ValueError("indicator_id must be non-empty")
        _finite(self.threshold, "threshold")
        _positive_int(self.lookback_period, "lookback_period")
        if (isinstance(self.initial_delay, bool)
                or not isinstance(self.initial_delay, int)
                or self.initial_delay < 0):
            raise ValueError("initial_delay must be a nonnegative integer")
        if self.initial_delay_mode not in ("continuous", "recheck"):
            raise ValueError("initial_delay_mode must be continuous or recheck")
        if self.lookback_scope not in ("market", "position"):
            raise ValueError("lookback_scope must be market or position")
        if self.comparison not in ("le", "ge", "lt", "gt", "eq", "ne"):
            raise ValueError("comparison must be le/ge/lt/gt/eq/ne")
        for name in ("lower_bound", "upper_bound"):
            if getattr(self, name) is not None:
                _finite(getattr(self, name), name)
        low, high = self.lower_bound, self.upper_bound
        if low is not None and high is not None and low > high:
            raise ValueError("lower_bound must not exceed upper_bound")
        if low == high == self.threshold and self.comparison == "ne":
            raise ValueError("Bounds and comparison define an empty interval")
        if (low is not None and (
                self.comparison in ("le", "eq") and low > self.threshold
                or self.comparison == "lt" and low >= self.threshold)
                or high is not None and (
                    self.comparison in ("ge", "eq") and high < self.threshold
                    or self.comparison == "gt" and high <= self.threshold)):
            raise ValueError("Bounds and comparison define an empty interval")
        if self.output is not None and self.output_column is not None and self.output != self.output_column:
            raise ValueError("output and output_column must agree")
        # Delegate weight validation to the existing scoring contract.
        validated = ConfluenceScoreRule(
            condition("_match", "eq", value=True),
            {} if self.group_weights is None else self.group_weights,
        )
        object.__setattr__(self, "group_weights", validated.group_weights)

    @property
    def selected_output(self):
        return self.output_column if self.output_column is not None else self.output

    def match(self, values):
        import operator

        matched = getattr(operator, self.comparison)(values, self.threshold)
        if self.lower_bound is not None:
            matched &= values >= self.lower_bound
        if self.upper_bound is not None:
            matched &= values <= self.upper_bound
        return matched


@dataclass(frozen=True)
class ConfluenceScoreConfig:
    rules: Mapping[str, IndicatorRule]
    group_aggregation: Mapping[str, str] = field(default_factory=dict)
    group_thresholds: Mapping[str, float] = field(default_factory=dict)
    override_triggers: Expression | None = None
    requirements: tuple[Requirement, ...] = ()
    vetoes: tuple[Veto, ...] = ()
    id: str | None = None
    side: SignalSide | None = None
    scale_in_stage: int | None = None
    symbols: tuple[str, ...] = ()
    initial_delay: int = 0
    initial_delay_mode: Literal["continuous", "recheck"] = "continuous"
    required_rules: tuple[str, ...] = ()
    blocking_rules: tuple[str, ...] = ()
    gates: tuple[str, ...] = ()
    readiness_policy: Literal["all_rules", "qualification_paths"] = "all_rules"

    def __reduce__(self):
        return reduce_immutable_dataclass(self)

    def __post_init__(self):
        if self.readiness_policy not in ("all_rules", "qualification_paths"):
            raise ValueError(
                "readiness_policy must be all_rules or qualification_paths"
            )
        if (isinstance(self.initial_delay, bool)
                or not isinstance(self.initial_delay, int)
                or self.initial_delay < 0):
            raise ValueError("initial_delay must be a nonnegative integer")
        if self.initial_delay_mode not in ("continuous", "recheck"):
            raise ValueError(
                "initial_delay_mode must be continuous or recheck"
            )
        if self.id is not None and (not isinstance(self.id, str) or not self.id.strip()):
            raise ValueError("Card id must be non-empty")
        if self.side is not None:
            object.__setattr__(self, "side", SignalSide.from_value(self.side))
        if self.scale_in_stage is not None:
            if (isinstance(self.scale_in_stage, bool)
                    or not isinstance(self.scale_in_stage, int)
                    or self.scale_in_stage < 0):
                raise ValueError("scale_in_stage must be a nonnegative integer")
            if self.side is not SignalSide.SCALE_IN:
                raise ValueError(
                    "scale_in_stage requires side=SignalSide.SCALE_IN"
                )
        if (not isinstance(self.symbols, (list, tuple))
                or any(not isinstance(symbol, str) or not symbol.strip()
                       or symbol != symbol.strip() for symbol in self.symbols)):
            raise ValueError("symbols must contain non-empty target symbols")
        symbols = tuple(symbol.upper() for symbol in self.symbols)
        if (any("/" in symbol for symbol in symbols)
                or len(set(symbols)) != len(symbols)):
            raise ValueError(
                "symbols must contain unique target symbols, not pairs"
            )
        object.__setattr__(self, "symbols", symbols)
        if not isinstance(self.rules, Mapping) or not all(
            isinstance(rule, IndicatorRule) for rule in self.rules.values()
        ):
            raise TypeError("rules must map names to IndicatorRule instances")
        if any(rule.lookback_scope == "position" for rule in self.rules.values()):
            if self.side not in (
                SignalSide.CLOSE_LONG, SignalSide.CLOSE_SHORT,
            ):
                raise ValueError("Position-scoped lookbacks require close_long or close_short")
        for name in ("rules", "group_aggregation", "group_thresholds"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "vetoes", tuple(self.vetoes))
        for field_name in ("required_rules", "blocking_rules", "gates"):
            names = getattr(self, field_name)
            if (not isinstance(names, (list, tuple))
                    or any(not isinstance(name, str) or not name.strip()
                           or name != name.strip() for name in names)):
                raise ValueError(
                    f"{field_name} must contain non-empty rule names"
                )
            if len(set(names)) != len(names):
                raise ValueError(f"{field_name} must contain unique rule names")
            unknown = set(names) - set(self.rules)
            if unknown:
                raise ValueError(
                    f"Unknown {field_name}: {sorted(unknown)}"
                )
            object.__setattr__(self, field_name, tuple(names))
        blockers = tuple(dict.fromkeys((*self.gates, *self.blocking_rules)))
        if set(self.required_rules) & set(blockers):
            raise ValueError("A rule cannot be both required and blocking")
        for names, gates, prefix in (
            (self.required_rules, self.requirements, "required_rule"),
            (blockers, self.vetoes, "blocking_rule"),
        ):
            if any(
                isinstance(gate, (Requirement, Veto))
                and gate.name == f"{prefix}:{name}"
                for gate in gates for name in names
            ):
                raise ValueError(f"{prefix} gate names are already configured")
        self.compile("_validate")
        for gate in (*self.requirements, *self.vetoes):
            _validate_match_expression(gate.expression, set(self.rules))
        if self.override_triggers is not None:
            _validate_match_expression(self.override_triggers, set(self.rules))

    def compile(self, name):
        """Bind native rolling-match booleans to the existing scoring engine.

        Requirements/vetoes may use independent conditions on named rule
        matches; overrides retain the existing Rule/Threshold expressions.
        Named required rules and gates compile into the same hard gates.
        blocking_rules remains a compatible alias; overlapping gates run once.
        """
        return ConfluenceScoreCard(
            name=name,
            rules={
                key: ConfluenceScoreRule(
                    condition(key, "eq", value=True),
                    {} if rule.group_weights is None else rule.group_weights,
                )
                for key, rule in self.rules.items()
            },
            group_aggregation=self.group_aggregation,
            group_thresholds=self.group_thresholds,
            override_triggers=self.override_triggers,
            requirements=self.requirements + tuple(
                Requirement(
                    f"required_rule:{key}", condition(key, "eq", value=True),
                )
                for key in self.required_rules
            ),
            vetoes=self.vetoes + tuple(
                Veto(
                    f"blocking_rule:{key}", condition(key, "eq", value=True),
                )
                for key in dict.fromkeys((*self.gates, *self.blocking_rules))
            ),
        )


@dataclass(frozen=True)
class IndicatorEvaluation:
    values: Mapping[str, Mapping[str, float]]
    cards: Mapping[str, Mapping]
    ready: Mapping[str, bool]
    rule_readiness: Mapping[str, Mapping[str, bool]] = field(default_factory=dict)
