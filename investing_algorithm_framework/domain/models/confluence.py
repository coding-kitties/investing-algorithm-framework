"""Declarative, explainable confluence scoring for strategy decisions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from enum import Enum
import json
from textwrap import wrap
from typing import Any, Literal, Mapping


CONFLUENCE_CARD_VERSION = 1


class Operator(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    BETWEEN = "between"


@dataclass(frozen=True)
class EvaluationContext:
    """Current and previous indicator values supplied by a strategy."""

    values: Mapping[str, Any]
    previous_values: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def _key(name: str, timeframe: str | None) -> str:
        return f"{timeframe}:{name}" if timeframe else name

    def get(self, name: str, *, timeframe: str | None = None) -> Any:
        return self.values[self._key(name, timeframe)]

    def previous(self, name: str, *, timeframe: str | None = None) -> Any:
        return self.previous_values[self._key(name, timeframe)]


class Expression:
    """Base class for composable logical expressions."""

    def evaluate(self, context: EvaluationContext) -> bool:
        raise NotImplementedError

    def evaluate_series(self, dataframe):
        """Evaluate built-in expressions as nullable pandas booleans."""
        from .confluence_frame import evaluate_expression_series

        return evaluate_expression_series(self, dataframe)


@dataclass(frozen=True)
class Condition:
    """A serializable comparison between an indicator and a value/reference."""

    indicator: str
    operator: Operator
    value: Any = None
    reference: str | None = None
    timeframe: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operator, Operator):
            object.__setattr__(self, "operator", Operator(self.operator))
        if not self.indicator:
            raise ValueError("Condition.indicator must be non-empty")
        if self.reference is not None and self.value is not None:
            raise ValueError(
                "Condition accepts either value or reference, not both"
            )
        if self.operator is Operator.BETWEEN:
            if self.reference is not None:
                raise ValueError("BETWEEN does not support reference")
            if (
                not isinstance(self.value, (tuple, list))
                or len(self.value) != 2
            ):
                raise ValueError(
                    "BETWEEN value must contain exactly two bounds"
                )
            object.__setattr__(self, "value", tuple(self.value))
        try:
            json.dumps(self.value, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Condition.value must be JSON serializable"
            ) from error

    def evaluate(self, context: EvaluationContext) -> bool:
        lhs = context.get(self.indicator, timeframe=self.timeframe)
        rhs = (
            context.get(self.reference, timeframe=self.timeframe)
            if self.reference is not None
            else self.value
        )

        if self.operator is Operator.GT:
            return lhs > rhs
        if self.operator is Operator.GTE:
            return lhs >= rhs
        if self.operator is Operator.LT:
            return lhs < rhs
        if self.operator is Operator.LTE:
            return lhs <= rhs
        if self.operator is Operator.EQ:
            return lhs == rhs
        if self.operator is Operator.NEQ:
            return lhs != rhs
        if self.operator is Operator.BETWEEN:
            low, high = self.value
            return low <= lhs <= high

        previous_lhs = context.previous(
            self.indicator, timeframe=self.timeframe
        )
        previous_rhs = (
            context.previous(self.reference, timeframe=self.timeframe)
            if self.reference is not None
            else self.value
        )
        if self.operator is Operator.CROSS_ABOVE:
            return previous_lhs <= previous_rhs and lhs > rhs
        if self.operator is Operator.CROSS_BELOW:
            return previous_lhs >= previous_rhs and lhs < rhs
        raise ValueError(f"Unsupported operator: {self.operator}")


@dataclass(frozen=True)
class ConditionExpression(Expression):
    condition: Condition

    def evaluate(self, context: EvaluationContext) -> bool:
        return self.condition.evaluate(context)


def condition(
    indicator: str,
    operator: Operator | str,
    *,
    value: Any = None,
    reference: str | None = None,
    timeframe: str | None = None,
    name: str | None = None,
) -> ConditionExpression:
    """Build a composable expression using Condition's validation."""
    return ConditionExpression(Condition(
        indicator=indicator,
        operator=operator,
        value=value,
        reference=reference,
        timeframe=timeframe,
        name=name,
    ))


@dataclass(frozen=True)
class AllOf(Expression):
    expressions: tuple[Expression, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expressions", tuple(self.expressions))
        if not self.expressions:
            raise ValueError("AllOf requires at least one expression")

    def evaluate(self, context: EvaluationContext) -> bool:
        return all(
            expression.evaluate(context) for expression in self.expressions
        )


@dataclass(frozen=True)
class AnyOf(Expression):
    expressions: tuple[Expression, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expressions", tuple(self.expressions))
        if not self.expressions:
            raise ValueError("AnyOf requires at least one expression")

    def evaluate(self, context: EvaluationContext) -> bool:
        return any(
            expression.evaluate(context) for expression in self.expressions
        )


@dataclass(frozen=True)
class Not(Expression):
    expression: Expression

    def evaluate(self, context: EvaluationContext) -> bool:
        return not self.expression.evaluate(context)


@dataclass(frozen=True)
class AtLeast(Expression):
    minimum: int
    expressions: tuple[Expression, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expressions", tuple(self.expressions))
        if self.minimum < 1:
            raise ValueError("AtLeast.minimum must be at least 1")
        if self.minimum > len(self.expressions):
            raise ValueError("AtLeast.minimum cannot exceed expression count")

    def evaluate(self, context: EvaluationContext) -> bool:
        return sum(
            expression.evaluate(context) for expression in self.expressions
        ) >= self.minimum


@dataclass(frozen=True)
class PrimaryGroup:
    expression: Expression | None = None
    name: str = "primary"
    rules: tuple[ScoreRule, ...] = ()
    minimum_matches: int = 1
    minimum_score: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(self.rules))
        if self.expression is not None:
            if self.rules or self.minimum_score is not None \
                    or self.minimum_matches != 1:
                raise ValueError("Use either a primary expression or rules")
        else:
            _validate_group(self)

    def evaluate(self, context: EvaluationContext) -> bool:
        if self.expression is not None:
            return self.expression.evaluate(context)
        return _evaluate_group(self, context, "primary")[0].passed


class ScoreType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class ScoreRule:
    name: str
    expression: Expression
    points: float
    score_type: ScoreType = ScoreType.POSITIVE
    group: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.score_type, ScoreType):
            object.__setattr__(self, "score_type", ScoreType(self.score_type))
        if not self.name:
            raise ValueError("ScoreRule.name must be non-empty")
        if self.score_type is ScoreType.POSITIVE and self.points < 0:
            raise ValueError("POSITIVE ScoreRule points cannot be negative")
        if self.score_type is ScoreType.NEGATIVE and self.points > 0:
            raise ValueError("NEGATIVE ScoreRule points cannot be positive")


@dataclass(frozen=True)
class Requirement:
    name: str
    expression: Expression


@dataclass(frozen=True)
class EvidenceGroup:
    """Scoring evidence; omitted thresholds make its contribution optional."""

    name: str
    rules: tuple[ScoreRule, ...]
    minimum_matches: int = 0
    minimum_score: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(self.rules))
        _validate_group(self)


def _validate_group(group) -> None:
    if not isinstance(group.name, str) or not group.name:
        raise ValueError("Group name must be non-empty")
    if not group.rules or not all(
        isinstance(rule, ScoreRule) for rule in group.rules
    ):
        raise ValueError("Group rules must contain ScoreRule instances")
    if type(group.minimum_matches) is not int or not (
        0 <= group.minimum_matches <= len(group.rules)
    ):
        raise ValueError(
            "minimum_matches must be an integer within rule count"
        )
    if group.minimum_score is not None and (
        isinstance(group.minimum_score, bool)
        or not isinstance(group.minimum_score, (int, float))
        or not isfinite(group.minimum_score)
    ):
        raise ValueError("Group minimum_score must be finite or None")


@dataclass(frozen=True)
class GroupEvaluation:
    name: str
    category: Literal["primary", "secondary"]
    matches: int
    score: float
    minimum_matches: int
    minimum_score: float | None
    passed: bool


def _evaluate_group(group, context, category):
    evaluations = tuple(
        RuleEvaluation(
            name=rule.name,
            matched=matched,
            points=float(rule.points) if matched else 0.0,
            group=rule.group or group.name,
            score_type=rule.score_type,
        )
        for rule in group.rules
        for matched in (bool(rule.expression.evaluate(context)),)
    )
    matches = sum(item.matched for item in evaluations)
    score = sum(item.points for item in evaluations)
    return GroupEvaluation(
        name=group.name,
        category=category,
        matches=matches,
        score=score,
        minimum_matches=group.minimum_matches,
        minimum_score=group.minimum_score,
        passed=(
            matches >= group.minimum_matches
            and (group.minimum_score is None or score >= group.minimum_score)
        ),
    ), evaluations


def _group_to_dict(group):
    return {
        "name": group.name,
        "rules": [
            {
                "name": rule.name,
                "expression": _expression_to_dict(rule.expression),
                "points": rule.points,
                "score_type": rule.score_type.value,
                "group": rule.group,
            }
            for rule in group.rules
        ],
        "minimum_matches": group.minimum_matches,
        "minimum_score": group.minimum_score,
    }


def _group_from_dict(data, group_type):
    return group_type(
        name=data["name"],
        rules=tuple(
            ScoreRule(
                name=rule["name"],
                expression=_expression_from_dict(rule["expression"]),
                points=rule["points"],
                score_type=rule.get("score_type", "positive"),
                group=rule.get("group"),
            )
            for rule in data["rules"]
        ),
        minimum_matches=data.get(
            "minimum_matches", 1 if group_type is PrimaryGroup else 0
        ),
        minimum_score=data.get("minimum_score"),
    )


@dataclass(frozen=True)
class Veto:
    name: str
    expression: Expression


@dataclass(frozen=True)
class RuleEvaluation:
    name: str
    matched: bool
    points: float = 0.0
    category: Literal["primary", "score", "requirement", "veto"] = "score"
    group: str | None = None
    score_type: ScoreType | None = None


@dataclass(frozen=True)
class ConfluenceResult:
    card_name: str
    primary_triggered: bool
    requirements_passed: bool
    veto_triggered: bool
    score: float
    minimum_score: float
    qualified: bool
    evaluations: tuple[RuleEvaluation, ...] = ()
    groups: tuple[GroupEvaluation, ...] = ()

    @property
    def secondary_passed(self) -> bool:
        return all(
            group.passed for group in self.groups
            if group.category == "secondary"
        )

    @property
    def decision(self) -> Literal["QUALIFIED", "REJECTED"]:
        return "QUALIFIED" if self.qualified else "REJECTED"

    @property
    def score_margin(self) -> float:
        return self.score - self.minimum_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_name": self.card_name,
            "primary_triggered": self.primary_triggered,
            "requirements_passed": self.requirements_passed,
            "veto_triggered": self.veto_triggered,
            "score": self.score,
            "minimum_score": self.minimum_score,
            "qualified": self.qualified,
            "decision": self.decision,
            "groups": [asdict(group) for group in self.groups],
            "secondary_passed": self.secondary_passed,
            "evaluations": [
                {
                    "name": evaluation.name,
                    "matched": evaluation.matched,
                    "points": evaluation.points,
                    "category": evaluation.category,
                    "group": evaluation.group,
                    "score_type": (
                        evaluation.score_type.value
                        if evaluation.score_type is not None else None
                    ),
                }
                for evaluation in self.evaluations
            ],
        }


@dataclass(frozen=True)
class ConfluenceCard:
    """A pure decision model; execution and position sizing remain external."""

    name: str
    primary: PrimaryGroup
    scoring: tuple[ScoreRule, ...] = ()
    requirements: tuple[Requirement, ...] = ()
    vetoes: tuple[Veto, ...] = ()
    minimum_score: float = 0.0
    version: int = CONFLUENCE_CARD_VERSION
    secondary: tuple[EvidenceGroup, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ConfluenceCard.name must be non-empty")
        object.__setattr__(self, "scoring", tuple(self.scoring))
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "vetoes", tuple(self.vetoes))
        object.__setattr__(self, "secondary", tuple(self.secondary))
        names = [self.primary.name] + [
            group.name for group in self.secondary
        ]
        if len(names) != len(set(names)):
            raise ValueError(
                "Primary and secondary group names must be unique"
            )

    def __str__(self) -> str:
        """Render the definition without evaluation or mutation."""
        lines = [
            f"ConfluenceCard: {self.name}",
            f"Minimum total score: {self.minimum_score:g}",
        ]

        def append_rules(rules):
            for rule in rules:
                label = f" [{rule.group}]" if rule.group else ""
                lines.append(f"  {rule.points:+g}  {rule.name}{label}")
                lines.append(f"      {_format_expression(rule.expression)}")

        def append_group(label, group):
            constraints = []
            if group.minimum_matches:
                constraints.append(f"matches >= {group.minimum_matches}")
            if group.minimum_score is not None:
                constraints.append(f"score >= {group.minimum_score:g}")
            gates = ", ".join(constraints) if constraints else "optional"
            lines.extend(("", f"{label}: {group.name} ({gates})"))
            append_rules(group.rules)

        if self.primary.expression is not None:
            lines.extend((
                "", f"Primary: {self.primary.name} (required)",
                f"  {_format_expression(self.primary.expression)}",
            ))
        else:
            append_group("Primary", self.primary)
        for group in self.secondary:
            append_group("Secondary", group)
        if self.scoring:
            lines.extend(("", "Additional scoring:"))
            append_rules(self.scoring)
        if self.requirements:
            lines.extend(("", "Requirements (all must match):"))
            for requirement in self.requirements:
                lines.append(f"  {requirement.name}")
                lines.append(
                    f"      {_format_expression(requirement.expression)}"
                )
        if self.vetoes:
            lines.extend(("", "Vetoes (any match rejects):"))
            for veto in self.vetoes:
                lines.append(f"  {veto.name}")
                lines.append(f"      {_format_expression(veto.expression)}")
        lines = [
            part.expandtabs(4)
            for line in lines
            for part in (line.splitlines() or [""])
        ]
        width = min(74, max(48, max(map(len, lines))))
        border = "+" + "=" * (width + 2) + "+"
        separator = "+" + "-" * (width + 2) + "+"
        rendered = [border]
        for line in lines:
            if not line:
                rendered.append(separator)
                continue
            indentation = len(line) - len(line.lstrip())
            for part in wrap(
                line, width=width,
                subsequent_indent=" " * min(indentation, width // 2),
            ):
                rendered.append(f"| {part:<{width}} |")
        rendered.append(border)
        return "\n".join(rendered)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical, versioned strategy definition."""
        return {
            "confluence_card_version": self.version,
            "name": self.name,
            "primary": {
                "name": self.primary.name,
                "expression": _expression_to_dict(self.primary.expression),
            } if self.primary.expression is not None else _group_to_dict(
                self.primary
            ),
            "secondary": [_group_to_dict(group) for group in self.secondary],
            "scoring": [
                {
                    "name": rule.name,
                    "expression": _expression_to_dict(rule.expression),
                    "points": rule.points,
                    "score_type": rule.score_type.value,
                    "group": rule.group,
                }
                for rule in self.scoring
            ],
            "requirements": [
                {
                    "name": requirement.name,
                    "expression": _expression_to_dict(requirement.expression),
                }
                for requirement in self.requirements
            ],
            "vetoes": [
                {
                    "name": veto.name,
                    "expression": _expression_to_dict(veto.expression),
                }
                for veto in self.vetoes
            ],
            "minimum_score": self.minimum_score,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConfluenceCard":
        primary = data["primary"]
        return cls(
            name=data["name"],
            primary=PrimaryGroup(
                name=primary.get("name", "primary"),
                expression=_expression_from_dict(primary["expression"]),
            ) if "expression" in primary else _group_from_dict(
                primary, PrimaryGroup
            ),
            secondary=tuple(
                _group_from_dict(group, EvidenceGroup)
                for group in data.get("secondary", [])
            ),
            scoring=tuple(
                ScoreRule(
                    name=rule["name"],
                    expression=_expression_from_dict(rule["expression"]),
                    points=rule["points"],
                    score_type=ScoreType(rule.get("score_type", "positive")),
                    group=rule.get("group"),
                )
                for rule in data.get("scoring", [])
            ),
            requirements=tuple(
                Requirement(
                    name=requirement["name"],
                    expression=_expression_from_dict(
                        requirement["expression"]
                    ),
                )
                for requirement in data.get("requirements", [])
            ),
            vetoes=tuple(
                Veto(
                    name=veto["name"],
                    expression=_expression_from_dict(veto["expression"]),
                )
                for veto in data.get("vetoes", [])
            ),
            minimum_score=data.get("minimum_score", 0.0),
            version=data.get(
                "confluence_card_version", CONFLUENCE_CARD_VERSION
            ),
        )

    def evaluate_series(self, dataframe):
        """Batch score, available, and qualified columns on the input index.

        Rows must already be in chronological order. Any required null or
        missing crossing history makes the card unavailable for that row.
        """
        from .confluence_frame import evaluate_card_series

        return evaluate_card_series(self, dataframe)

    def evaluate(self, context: EvaluationContext) -> ConfluenceResult:
        evaluations: list[RuleEvaluation] = []

        requirement_matches = []
        for requirement in self.requirements:
            matched = requirement.expression.evaluate(context)
            requirement_matches.append(matched)
            evaluations.append(RuleEvaluation(
                name=requirement.name,
                matched=matched,
                category="requirement",
            ))
        requirements_passed = all(requirement_matches)

        groups = []
        score = 0.0
        if self.primary.expression is not None:
            primary_triggered = self.primary.evaluate(context)
        else:
            group_result, rule_results = _evaluate_group(
                self.primary, context, "primary"
            )
            groups.append(group_result)
            evaluations.extend(rule_results)
            score += group_result.score
            primary_triggered = group_result.passed
        evaluations.append(RuleEvaluation(
            name=self.primary.name,
            matched=primary_triggered,
            category="primary",
        ))

        veto_matches = []
        for veto in self.vetoes:
            matched = veto.expression.evaluate(context)
            veto_matches.append(matched)
            evaluations.append(RuleEvaluation(
                name=veto.name,
                matched=matched,
                category="veto",
            ))
        veto_triggered = any(veto_matches)

        secondary_passed = True
        for group in self.secondary:
            group_result, rule_results = _evaluate_group(
                group, context, "secondary"
            )
            groups.append(group_result)
            evaluations.extend(rule_results)
            score += group_result.score
            secondary_passed = secondary_passed and group_result.passed

        for rule in self.scoring:
            matched = rule.expression.evaluate(context)
            contribution = float(rule.points) if matched else 0.0
            score += contribution
            evaluations.append(RuleEvaluation(
                name=rule.name,
                matched=matched,
                points=contribution,
                category="score",
                group=rule.group,
                score_type=rule.score_type,
            ))

        qualified = (
            primary_triggered
            and secondary_passed
            and requirements_passed
            and not veto_triggered
            and score >= self.minimum_score
        )
        return ConfluenceResult(
            card_name=self.name,
            primary_triggered=primary_triggered,
            requirements_passed=requirements_passed,
            veto_triggered=veto_triggered,
            score=score,
            minimum_score=float(self.minimum_score),
            qualified=qualified,
            evaluations=tuple(evaluations),
            groups=tuple(groups),
        )


def _format_expression(expression: Expression) -> str:
    if isinstance(expression, ConditionExpression):
        predicate = expression.condition
        prefix = f"{predicate.timeframe}:" if predicate.timeframe else ""
        left = f"{prefix}{predicate.indicator}"
        if predicate.operator is Operator.BETWEEN:
            low, high = predicate.value
            text = f"{json.dumps(low)} <= {left} <= {json.dumps(high)}"
        else:
            operators = {
                Operator.GT: ">", Operator.GTE: ">=",
                Operator.LT: "<", Operator.LTE: "<=",
                Operator.EQ: "==", Operator.NEQ: "!=",
                Operator.CROSS_ABOVE: "crosses above",
                Operator.CROSS_BELOW: "crosses below",
            }
            right = (
                f"{prefix}{predicate.reference}"
                if predicate.reference is not None
                else json.dumps(predicate.value)
            )
            text = f"{left} {operators[predicate.operator]} {right}"
        return f"{predicate.name}: {text}" if predicate.name else text
    if isinstance(expression, Not):
        return f"NOT ({_format_expression(expression.expression)})"
    if isinstance(expression, (AllOf, AnyOf, AtLeast)):
        if isinstance(expression, AllOf):
            label = "ALL OF"
        elif isinstance(expression, AnyOf):
            label = "ANY OF"
        else:
            label = f"AT LEAST {expression.minimum} OF"
        children = "; ".join(
            _format_expression(child) for child in expression.expressions
        )
        return f"{label} ({children})"
    return f"<{type(expression).__name__}>"


def _expression_to_dict(expression: Expression) -> dict[str, Any]:
    if isinstance(expression, ConditionExpression):
        condition = expression.condition
        return {
            "type": "condition",
            "indicator": condition.indicator,
            "operator": condition.operator.value,
            "value": condition.value,
            "reference": condition.reference,
            "timeframe": condition.timeframe,
            "name": condition.name,
        }
    if isinstance(expression, AllOf):
        return {
            "type": "all_of",
            "expressions": [
                _expression_to_dict(item) for item in expression.expressions
            ],
        }
    if isinstance(expression, AnyOf):
        return {
            "type": "any_of",
            "expressions": [
                _expression_to_dict(item) for item in expression.expressions
            ],
        }
    if isinstance(expression, Not):
        return {
            "type": "not",
            "expression": _expression_to_dict(expression.expression),
        }
    if isinstance(expression, AtLeast):
        return {
            "type": "at_least",
            "minimum": expression.minimum,
            "expressions": [
                _expression_to_dict(item) for item in expression.expressions
            ],
        }
    raise TypeError(
        f"Unsupported expression type: {type(expression).__name__}"
    )


def _expression_from_dict(data: Mapping[str, Any]) -> Expression:
    expression_type = data.get("type")
    if expression_type == "condition":
        return ConditionExpression(Condition(
            indicator=data["indicator"],
            operator=Operator(data["operator"]),
            value=data.get("value"),
            reference=data.get("reference"),
            timeframe=data.get("timeframe"),
            name=data.get("name"),
        ))
    if expression_type in ("all_of", "any_of", "at_least"):
        expressions = tuple(
            _expression_from_dict(item) for item in data["expressions"]
        )
        if expression_type == "all_of":
            return AllOf(expressions)
        if expression_type == "any_of":
            return AnyOf(expressions)
        return AtLeast(data["minimum"], expressions)
    if expression_type == "not":
        return Not(_expression_from_dict(data["expression"]))
    raise ValueError(f"Unsupported expression type: {expression_type!r}")
