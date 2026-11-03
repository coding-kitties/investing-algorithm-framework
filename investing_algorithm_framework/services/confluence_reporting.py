"""Recorded scoring definitions, without re-evaluating indicator predicates."""
from copy import deepcopy

from investing_algorithm_framework.domain import (
    ConfluenceScoreCard, DecisionTrace, DecisionTraceEntry,
)
from investing_algorithm_framework.domain.models.confluence import (
    _format_expression,
)


def skipped_confluence_trace(name, side, reason, indicator_snapshot):
    entries = [
        DecisionTraceEntry("signal_side", side.value, group="decision"),
        DecisionTraceEntry("signal_selected", False, group="decision"),
        DecisionTraceEntry("evaluation_status", "skipped", group="decision"),
        DecisionTraceEntry("signal_reason", reason, group="decision"),
    ]
    entries.extend(
        DecisionTraceEntry(
            name, value.item() if hasattr(value, "item") else value,
            group="indicators",
        )
        for name, value in indicator_snapshot.items()
    )
    return DecisionTrace(
        entries=entries, summary=f"{name}: not triggered; evaluation skipped ({reason})",
    )


def confluence_report_details(card, payload):
    record = deepcopy(payload)
    definitions = {}
    maxima = {}
    if isinstance(card, ConfluenceScoreCard):
        for name, rule in card.rules.items():
            if not rule.group_weights:
                definitions[None, name] = (rule.expression, 0.0)
            for group, weight in rule.group_weights.items():
                definitions[group, name] = (rule.expression, weight)
        aggregation = dict(card.group_aggregation)
        record["overall_minimum_score"] = None
        thresholds = ", ".join(
            f"{group} >= {threshold:g}"
            for group, threshold in card.group_thresholds.items()
        )
        qualification = f"All group thresholds: {thresholds}" if thresholds else "Normal path disabled"
        if card.override_triggers is not None:
            qualification += f"; OR override: {_format_expression(card.override_triggers)}"
    else:
        aggregation = {}
        for group in (card.primary, *card.secondary):
            for rule in group.rules:
                definitions[rule.group or group.name, rule.name] = (
                    rule.expression, rule.points,
                )
        for rule in card.scoring:
            definitions[rule.group, rule.name] = (rule.expression, rule.points)
        record["overall_minimum_score"] = card.minimum_score
        qualification = "Primary and secondary gates, and overall minimum"
    for group in dict.fromkeys(key[0] for key in definitions):
        if group is None:
            continue
        weights = [
            max(0., weight) for (name, _), (_, weight) in definitions.items()
            if name == group
        ]
        maxima[group] = (
            max(weights) if aggregation.get(group) == "max" else sum(weights)
        )
    record["maximum_score"] = sum(maxima.values())
    record["qualification_description"] = (
        qualification + "; requirements must pass and no veto may trigger"
    )
    for group in record["groups"]:
        if group["name"] in maxima:
            group["maximum_score"] = maxima[group["name"]]
            group["aggregation"] = aggregation.get(group["name"], "sum")
    for evaluation in record["evaluations"]:
        definition = definitions.get((evaluation["group"], evaluation["name"]))
        if evaluation["category"] != "score" or definition is None:
            continue
        expression, weight = definition
        evaluation.update(
            weight=weight, maximum_points=max(0., weight),
            condition=_format_expression(expression),
            required=any(
                item.expression == expression for item in card.requirements
            ),
        )
    return record
