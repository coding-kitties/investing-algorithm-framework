"""Named, multi-group confluence scoring with explicit override paths."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping
from ..utils.immutable import reduce_immutable_dataclass

from .confluence import (
    AllOf, AnyOf, AtLeast, ConfluenceResult, EvaluationContext, Expression,
    GroupEvaluation, Not, Requirement, RuleEvaluation, ScoreType, Veto,
    _expression_from_dict, _expression_to_dict, _format_expression, _render_card_box,
)

if TYPE_CHECKING:
    from ..indicators import ConfluenceScoreConfig, IndicatorConfig
    from .data import DataSource
    from .signal import SignalSide


def _name(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a non-empty name without surrounding whitespace")


def _number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _inspection_value_key(value: object) -> tuple:
    if isinstance(value, Mapping):
        return ("mapping", type(value), frozenset(
            (_inspection_value_key(key), _inspection_value_key(item))
            for key, item in value.items()
        ))
    if isinstance(value, (tuple, list)):
        return ("sequence", type(value), tuple(_inspection_value_key(item) for item in value))
    if is_dataclass(value) and not isinstance(value, type):
        return (type(value), tuple(
            (item.name, _inspection_value_key(getattr(value, item.name)))
            for item in fields(value)
        ))
    if value is None or type(value) in (str, bool, int, float):
        return ("value", type(value), value)
    # Opaque parameter objects cannot safely establish cross-symbol equivalence.
    return ("identity", type(value), id(value))


@dataclass(frozen=True)
class _ScoreContext(EvaluationContext):
    rule_matches: Mapping[str, bool] = field(default_factory=dict)
    group_scores: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule(Expression):
    """Reference the observed match of a named rule, not its credited points."""

    name: str

    def __post_init__(self) -> None:
        _name(self.name, "Rule.name")

    def evaluate(self, context: EvaluationContext) -> bool:
        if not isinstance(context, _ScoreContext):
            raise ValueError("Rule references require ConfluenceScoreCard evaluation")
        return context.rule_matches[self.name]


@dataclass(frozen=True)
class Threshold(Expression):
    """An inclusive comparison against an aggregated group score."""

    group: str
    value: float

    def __post_init__(self) -> None:
        _name(self.group, "Threshold.group")
        object.__setattr__(self, "value", _number(self.value, "Threshold.value"))

    def evaluate(self, context: EvaluationContext) -> bool:
        if not isinstance(context, _ScoreContext):
            raise ValueError("Threshold references require ConfluenceScoreCard evaluation")
        return context.group_scores[self.group] >= self.value


def _references(expression: Expression):
    if isinstance(expression, (Rule, Threshold)):
        yield expression
    elif isinstance(expression, (AllOf, AnyOf, AtLeast)):
        for child in expression.expressions:
            yield from _references(child)
    elif isinstance(expression, Not):
        yield from _references(expression.expression)


@dataclass(frozen=True)
class ConfluenceScoreRule:
    expression: Expression
    group_weights: Mapping[str, float]

    def __reduce__(self):
        return reduce_immutable_dataclass(self)

    def __post_init__(self) -> None:
        if not isinstance(self.expression, Expression):
            raise TypeError("Rule expression must be an Expression")
        if any(_references(self.expression)):
            raise ValueError("Scoring rule expressions cannot reference rule or group results")
        if not isinstance(self.group_weights, Mapping):
            raise ValueError("group_weights must be a mapping")
        weights = {}
        for group, weight in self.group_weights.items():
            _name(group, "Scoring group")
            weights[group] = _number(weight, "Group weight")
        object.__setattr__(self, "group_weights", MappingProxyType(dict(sorted(weights.items()))))


@dataclass(frozen=True)
class ConfluenceScoreCard:
    """Requirements AND no veto AND (normal thresholds OR override).

    Rule predicates are evaluated once. Max groups credit the first largest
    matching contribution, including negative evidence, without hiding matches.
    An empty normal-threshold mapping disables the normal path.
    """

    name: str
    rules: Mapping[str, ConfluenceScoreRule]
    group_thresholds: Mapping[str, float] = field(default_factory=dict)
    group_aggregation: Mapping[str, Literal["sum", "max"]] = field(default_factory=dict)
    override_triggers: Expression | None = None
    requirements: tuple[Requirement, ...] = ()
    vetoes: tuple[Veto, ...] = ()
    symbol: str | None = field(default=None, kw_only=True, compare=False)
    configuration: ConfluenceScoreConfig | None = field(
        default=None, kw_only=True, compare=False, repr=False,
    )
    indicator_configs: Mapping[str, IndicatorConfig] | None = field(
        default=None, kw_only=True, compare=False, repr=False,
    )
    data_sources: Mapping[str, DataSource] | None = field(
        default=None, kw_only=True, compare=False, repr=False,
    )
    symbol_cards: tuple[ConfluenceScoreCard, ...] | None = field(
        default=None, kw_only=True, compare=False, repr=False,
    )

    def __reduce__(self):
        return reduce_immutable_dataclass(self)

    def __post_init__(self) -> None:
        _name(self.name, "Card name")
        if not isinstance(self.rules, Mapping) or not self.rules:
            raise ValueError("rules must be a non-empty mapping")
        for name, rule in self.rules.items():
            _name(name, "Rule name")
            if name in {"score", "matches", "minimum_score", "minimum_matches", "passed"}:
                raise ValueError(f"Rule name is reserved for group evidence: {name}")
            if not isinstance(rule, ConfluenceScoreRule):
                raise TypeError("rules must contain ConfluenceScoreRule instances")
        groups = {group for rule in self.rules.values() for group in rule.group_weights}
        # These group names carry fixed meanings in DecisionTrace.
        if groups & {"decision", "indicators", "indicator_sources", "requirement", "veto", "qualification"}:
            raise ValueError("Scoring groups must not use reserved decision-trace group names")
        for values in (self.group_thresholds, self.group_aggregation):
            if not isinstance(values, Mapping):
                raise TypeError("Group settings must be mappings")
            if set(values) - groups:
                raise ValueError(f"Unknown scoring groups: {sorted(set(values) - groups)}")
        aggregation = {group: self.group_aggregation.get(group, "sum") for group in sorted(groups)}
        if any(method not in ("sum", "max") for method in aggregation.values()):
            raise ValueError("Group aggregation must be sum or max")
        thresholds = {
            group: _number(value, "Group threshold")
            for group, value in self.group_thresholds.items()
        }
        maxima = {}
        for group, method in aggregation.items():
            weights = [
                max(0.0, rule.group_weights[group])
                for rule in self.rules.values() if group in rule.group_weights
            ]
            maxima[group] = _number(sum(weights) if method == "sum" else max(weights), "Maximum group score")
        for group, threshold in thresholds.items():
            if threshold > maxima[group]:
                raise ValueError(f"{group} threshold exceeds maximum score {maxima[group]:g}")
        if not thresholds and self.override_triggers is None:
            raise ValueError("Configure group_thresholds or override_triggers")
        if self.override_triggers is not None:
            if not isinstance(self.override_triggers, Expression):
                raise TypeError("override_triggers must be an Expression")
            for reference in _references(self.override_triggers):
                if isinstance(reference, Rule) and reference.name not in self.rules:
                    raise ValueError(f"Unknown override rule: {reference.name}")
                if isinstance(reference, Threshold) and reference.group not in groups:
                    raise ValueError(f"Unknown override group: {reference.group}")
                if isinstance(reference, Threshold) and reference.value > maxima[reference.group]:
                    raise ValueError(f"Override threshold exceeds {reference.group} maximum score")
        requirements, vetoes = tuple(self.requirements), tuple(self.vetoes)
        for item in (*requirements, *vetoes):
            if not isinstance(item, (Requirement, Veto)):
                raise TypeError("Requirements and vetoes must use framework rule types")
            if any(_references(item.expression)):
                raise ValueError("Requirements and vetoes must use independent conditions")
        if not all(isinstance(item, Requirement) for item in requirements):
            raise TypeError("requirements must contain Requirement instances")
        if not all(isinstance(item, Veto) for item in vetoes):
            raise TypeError("vetoes must contain Veto instances")
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))
        object.__setattr__(self, "group_aggregation", MappingProxyType(aggregation))
        object.__setattr__(self, "group_thresholds", MappingProxyType(thresholds))
        object.__setattr__(self, "requirements", requirements)
        object.__setattr__(self, "vetoes", vetoes)
        if self.symbol_cards is not None:
            self._validate_merged_inspection()
        elif self.configuration is not None:
            self._validate_inspection()
        elif any(value is not None for value in (
            self.symbol, self.indicator_configs, self.data_sources,
        )):
            raise ValueError("Inspection metadata requires a configuration")

    def _validate_inspection(self) -> None:
        from ..indicators import ConfluenceScoreConfig, IndicatorConfig
        from .data import DataSource

        config = self.configuration
        if not isinstance(config, ConfluenceScoreConfig):
            raise TypeError("configuration must be ConfluenceScoreConfig")
        if not isinstance(self.symbol, str) or not self.symbol or self.symbol != self.symbol.strip().upper():
            raise ValueError("Inspection symbol must be a non-empty uppercase target")
        if config.side is None or set(config.rules) != set(self.rules):
            raise ValueError("Inspection configuration must match the scoring card and declare a side")
        indicators, sources = self.indicator_configs, self.data_sources
        if not isinstance(indicators, Mapping) or not isinstance(sources, Mapping):
            raise TypeError("Inspection requires indicator_configs and data_sources mappings")
        if set(indicators) != {rule.indicator_id for rule in config.rules.values()}:
            raise ValueError("Inspection indicators must match the configured rules")
        for name, indicator in indicators.items():
            if not isinstance(indicator, IndicatorConfig) or indicator.id != name:
                raise ValueError("Inspection indicator keys must match IndicatorConfig IDs")
            if not isinstance(indicator.data_source, str) or indicator.data_source not in sources:
                raise ValueError("Inspection indicators require resolved source identifiers")
        for name, source in sources.items():
            if not isinstance(source, DataSource) or source.get_identifier() != name:
                raise ValueError("Inspection source keys must match DataSource identifiers")
            if source.symbol is None or source.symbol.split("/")[0] != self.symbol:
                raise ValueError("Inspection sources must belong to the target symbol")
        object.__setattr__(self, "indicator_configs", MappingProxyType(dict(indicators)))
        object.__setattr__(self, "data_sources", MappingProxyType(dict(sources)))

    def _inspection_definition(self) -> tuple:
        config, indicators, sources = self.configuration, self.indicator_configs, self.data_sources
        assert config is not None and indicators is not None and sources is not None
        source_definitions = {}
        for name, indicator in indicators.items():
            identifier = indicator.data_source
            assert isinstance(identifier, str)
            source = sources[identifier]
            source_definitions[name] = {
                item.name: getattr(source, item.name)
                for item in fields(source) if item.name not in {"identifier", "symbol"}
            }
        return _inspection_value_key((
            self.to_dict(), replace(config, symbols=()),
            {
                name: replace(indicator, symbol=None, data_source=None)
                for name, indicator in indicators.items()
            },
            source_definitions,
        ))

    def _validate_merged_inspection(self) -> None:
        cards = self.symbol_cards
        if (
            not isinstance(cards, tuple) or len(cards) < 2
            or any(
                not isinstance(card, ConfluenceScoreCard)
                or card.configuration is None or card.symbol is None
                or card.symbol_cards is not None for card in cards
            )
        ):
            raise ValueError("Merged inspection requires at least two symbol-bound cards")
        if any(value is not None for value in (
            self.symbol, self.configuration, self.indicator_configs, self.data_sources,
        )):
            raise ValueError("Merged inspection metadata must be accessed through symbol_cards")
        if len({card.symbol for card in cards}) != len(cards):
            raise ValueError("Merged inspection symbols must be unique")
        definition = cards[0]._inspection_definition()
        if self.to_dict() != cards[0].to_dict() or any(
            card._inspection_definition() != definition for card in cards[1:]
        ):
            raise ValueError("Only identical inspection definitions can be merged")

    @property
    def symbols(self) -> tuple[str, ...]:
        if self.symbol_cards is not None:
            return tuple(symbol for card in self.symbol_cards for symbol in card.symbols)
        return (self.symbol,) if self.symbol is not None else ()

    @property
    def side(self) -> SignalSide | None:
        card = self.symbol_cards[0] if self.symbol_cards is not None else self
        return card.configuration.side if card.configuration is not None else None

    @property
    def scale_in_stage(self) -> int | None:
        card = self.symbol_cards[0] if self.symbol_cards is not None else self
        return card.configuration.scale_in_stage if card.configuration is not None else None

    def score_rules(self, matches: Mapping[str, bool]):
        contributions = {
            (group, name): weight if matches[name] else 0.0
            for name, rule in self.rules.items()
            for group, weight in rule.group_weights.items()
        }
        for group, method in self.group_aggregation.items():
            if method == "max":
                candidates = [
                    name for name, rule in self.rules.items()
                    if group in rule.group_weights and matches[name]
                ]
                winner = max(candidates, key=lambda name: contributions[group, name]) if candidates else None
                for key in contributions:
                    if key[0] == group and key[1] != winner:
                        contributions[key] = 0.0
        scores = {
            group: sum(value for (name, _), value in contributions.items() if name == group)
            for group in self.group_aggregation
        }
        for score in (*scores.values(), sum(scores.values())):
            _number(score, "Aggregated score")
        return scores, contributions

    def evaluate(self, context: EvaluationContext) -> ConfluenceResult:
        matches = {
            name: bool(rule.expression.evaluate(context))
            for name, rule in self.rules.items()
        }
        scores, _ = self.score_rules(matches)
        scored_context = _ScoreContext(
            context.values, context.previous_values, matches, scores,
        )
        override = self.override_triggers is not None and bool(self.override_triggers.evaluate(scored_context))
        return self.result_from_evidence(
            matches,
            tuple(bool(item.expression.evaluate(context)) for item in self.requirements),
            tuple(bool(item.expression.evaluate(context)) for item in self.vetoes),
            override,
        )

    def result_from_evidence(
        self, matches: Mapping[str, bool],
        requirement_matches: tuple[bool, ...], veto_matches: tuple[bool, ...],
        override: bool,
    ) -> ConfluenceResult:
        """Reconstruct a result from recorded matches, without evaluating predicates."""
        if set(matches) != set(self.rules) or any(type(value) is not bool for value in matches.values()):
            raise ValueError("Rule evidence must contain a boolean for every named rule")
        if len(requirement_matches) != len(self.requirements) or len(veto_matches) != len(self.vetoes):
            raise ValueError("Gate evidence does not match the card definition")
        if any(type(value) is not bool for value in (*requirement_matches, *veto_matches, override)):
            raise ValueError("Gate and override evidence must be boolean")
        scores, contributions = self.score_rules(matches)
        normal = bool(self.group_thresholds) and all(
            scores[group] >= threshold for group, threshold in self.group_thresholds.items()
        )
        evaluations = []
        for name, rule in self.rules.items():
            if not rule.group_weights:
                evaluations.append(RuleEvaluation(
                    name, matches[name], score_type=ScoreType.POSITIVE,
                ))
            for group, weight in rule.group_weights.items():
                evaluations.append(RuleEvaluation(
                    name, matches[name], points=contributions[group, name], group=group,
                    score_type=ScoreType.NEGATIVE if weight < 0 else ScoreType.POSITIVE,
                ))
        gates = [
            RuleEvaluation(item.name, matched, category="requirement")
            for item, matched in zip(self.requirements, requirement_matches)
        ] + [
            RuleEvaluation(item.name, matched, category="veto")
            for item, matched in zip(self.vetoes, veto_matches)
        ]
        requirements_passed = all(item.matched for item in gates if item.category == "requirement")
        veto_triggered = any(item.matched for item in gates if item.category == "veto")
        return ConfluenceResult(
            card_name=self.name, primary_triggered=normal or override,
            requirements_passed=requirements_passed, veto_triggered=veto_triggered,
            score=sum(scores.values()), minimum_score=0.0,
            qualified=requirements_passed and not veto_triggered and (normal or override),
            evaluations=tuple(evaluations + gates + [
                RuleEvaluation("qualification", normal or override, category="primary"),
                RuleEvaluation("normal_path", normal, group="qualification"),
                RuleEvaluation("override_path", override, group="qualification"),
            ]),
            groups=tuple(
                GroupEvaluation(
                    group, "score",
                    sum(matches[name] for name, rule in self.rules.items() if group in rule.group_weights),
                    score, 0, self.group_thresholds.get(group),
                    score >= self.group_thresholds[group] if group in self.group_thresholds else True,
                )
                for group, score in scores.items()
            ),
        )

    def evaluate_series(self, dataframe, *, backend="python"):
        from .confluence_frame import evaluate_score_card_series
        return evaluate_score_card_series(self, dataframe, backend=backend)

    def to_dict(self) -> dict:
        return {
            "confluence_score_card_version": 1,
            "name": self.name,
            "rule_order": list(self.rules),
            "rules": {
                name: {
                    "expression": _expression_to_dict(rule.expression),
                    "group_weights": dict(rule.group_weights),
                }
                for name, rule in self.rules.items()
            },
            "group_aggregation": dict(self.group_aggregation),
            "group_thresholds": dict(self.group_thresholds),
            "override_triggers": _expression_to_dict(self.override_triggers) if self.override_triggers else None,
            "requirements": [
                {"name": item.name, "expression": _expression_to_dict(item.expression)}
                for item in self.requirements
            ],
            "vetoes": [
                {"name": item.name, "expression": _expression_to_dict(item.expression)}
                for item in self.vetoes
            ],
        }

    @classmethod
    def from_dict(cls, value: Mapping) -> ConfluenceScoreCard:
        if value.get("confluence_score_card_version") != 1:
            raise ValueError("Unsupported confluence score card version")
        order = value.get("rule_order", list(value["rules"]))
        if (
            not isinstance(order, list)
            or any(not isinstance(name, str) for name in order)
            or len(order) != len(set(order))
            or set(order) != set(value["rules"])
        ):
            raise ValueError("rule_order must list each named rule exactly once")
        return cls(
            name=value["name"],
            rules={
                name: ConfluenceScoreRule(
                    _expression_from_dict(value["rules"][name]["expression"]), value["rules"][name]["group_weights"],
                )
                for name in order
            },
            group_thresholds=value.get("group_thresholds", {}),
            group_aggregation=value.get("group_aggregation", {}),
            override_triggers=_expression_from_dict(value["override_triggers"]) if value.get("override_triggers") is not None else None,
            requirements=tuple(
                Requirement(item["name"], _expression_from_dict(item["expression"]))
                for item in value.get("requirements", ())
            ),
            vetoes=tuple(
                Veto(item["name"], _expression_from_dict(item["expression"]))
                for item in value.get("vetoes", ())
            ),
        )

    def __str__(self) -> str:
        if self.configuration is not None or self.symbol_cards is not None:
            return self._inspection_string()
        lines = [f"ConfluenceScoreCard: {self.name}", "Qualification: requirements AND no veto AND (normal OR override)"]
        for name, rule in self.rules.items():
            lines.append(f"  {name}: {_format_expression(rule.expression)}; weights={dict(rule.group_weights)}")
        for group, method in self.group_aggregation.items():
            threshold = self.group_thresholds.get(group)
            lines.append(f"  {group}: {method}; " + (f"score >= {threshold:g}" if threshold is not None else "optional"))
        lines.append("Override: " + (_format_expression(self.override_triggers) if self.override_triggers else "none"))
        for label, items in (("Requirement", self.requirements), ("Veto", self.vetoes)):
            for item in items:
                lines.append(f"{label} {item.name}: {_format_expression(item.expression)}")
        return "\n".join(lines)

    def _inspection_string(self) -> str:
        inspections = self.symbol_cards if self.symbol_cards is not None else (self,)
        primary = inspections[0]
        config = primary.configuration
        indicators = primary.indicator_configs
        assert config is not None and config.side is not None
        assert indicators is not None
        symbol_label = (
            f"Symbols: {', '.join(self.symbols)}" if len(inspections) > 1
            else f"Symbol: {primary.symbol}"
        )
        lines = [
            f"ConfluenceScoreCard: {self.name}",
            f"{symbol_label} | Side: {config.side.value} | Stage: {config.scale_in_stage}",
            f"Readiness: {config.readiness_policy}",
            "Qualification: requirements AND no veto AND (normal OR override)",
        ]
        if config.initial_delay:
            lines.insert(2, f"Card delay: {config.initial_delay} evaluations ({config.initial_delay_mode})")
        operators = {"le": "<=", "ge": ">=", "lt": "<", "gt": ">", "eq": "==", "ne": "!="}
        rule_lines: dict[str, list[str]] = {}
        for name, rule in config.rules.items():
            indicator = indicators[rule.indicator_id]
            output = rule.selected_output or indicator.outputs[0]
            reference = f"{rule.indicator_id}.{output}"
            expression = f"{reference} {operators[rule.comparison]} {rule.threshold:g}"
            if rule.lower_bound is not None:
                expression += f" AND {reference} >= {rule.lower_bound:g}"
            if rule.upper_bound is not None:
                expression += f" AND {reference} <= {rule.upper_bound:g}"
            details = [
                f"  {name}: {expression}",
                f"    Delay: {rule.initial_delay} evaluations ({rule.initial_delay_mode})",
                f"    Lookback: {rule.lookback_period} native bars ({rule.lookback_scope})",
            ]
            for inspection in inspections:
                bound_indicators, sources = inspection.indicator_configs, inspection.data_sources
                assert bound_indicators is not None and sources is not None
                identifier = bound_indicators[rule.indicator_id].data_source
                assert isinstance(identifier, str)
                source = sources[identifier]
                assert source.time_frame is not None
                source_label = f"Source ({inspection.symbol})" if len(inspections) > 1 else "Source"
                details.append(
                    f"    {source_label}: {source.get_identifier()} | {source.symbol} | {source.market} | {source.time_frame.value}"
                )
            if indicator.calculate is not None:
                details.append(f"    Parameters: {dict(indicator.parameters)}")
            else:
                parameters = (
                    f"short={indicator.short_period}, long={indicator.long_period}, signal={indicator.signal_period}"
                    if indicator.indicator == "macd" else
                    f"period={indicator.period}, k_slowing={indicator.k_slowing}, d_period={indicator.d_period}"
                    if indicator.indicator == "stochastic" else
                    f"period={indicator.period}, scale={indicator.scale:g}"
                    if indicator.indicator == "z_score" else f"period={indicator.period}"
                )
                details.append(f"    Indicator: {indicator.indicator}; {parameters}")
            rule_lines[name] = details
        for group, method in self.group_aggregation.items():
            weights = [
                max(0.0, rule.group_weights[group])
                for rule in self.rules.values() if group in rule.group_weights
            ]
            capacity = sum(weights) if method == "sum" else max(weights)
            threshold = self.group_thresholds.get(group)
            gate = f"score >= {threshold:g}" if threshold is not None else "optional"
            lines.extend(("", f"Group {group}: {method}; {gate}; capacity={capacity:g}"))
            for name, rule in config.rules.items():
                weights = self.rules[name].group_weights
                if group not in weights:
                    continue
                details = rule_lines[name]
                lines.append(details[0])
                lines.append(f"    Weight: {weights[group]:g}")
                lines.extend(details[1:])
        unweighted = [
            name for name, rule in self.rules.items() if not rule.group_weights
        ]
        if unweighted:
            lines.extend(("", "Unweighted rules (no scoring contribution):"))
            for name in unweighted:
                lines.extend(rule_lines[name])
        lines.append("")
        lines.append("Override: " + (_format_expression(self.override_triggers) if self.override_triggers else "none"))
        for label, items in (("Requirement", self.requirements), ("Veto", self.vetoes)):
            for item in items:
                lines.append(f"{label} {item.name}: {_format_expression(item.expression)}")
        return _render_card_box(lines)
