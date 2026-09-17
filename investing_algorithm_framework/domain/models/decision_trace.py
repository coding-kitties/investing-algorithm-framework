"""Versioned, portable traces explaining strategy decisions.

A ``DecisionTrace`` is deliberately flat and JSON-only so dashboards,
notebooks, APIs, and persisted run reports can render it without knowing the
strategy's executable decision model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Union

# Every platform/tool that wants to render a decision trace without
# strategy-specific code should look for this key on a Signal's
# ``metadata`` — and, for a signal that was executed, on the
# resulting Order's ``metadata`` (``Signal.metadata`` flows into
# ``Order.metadata`` verbatim; see ``Signal.with_decision_trace``).
DECISION_TRACE_METADATA_KEY = "decision_trace"

# Bump only on breaking shape changes. Consumers should ignore
# unknown fields and degrade gracefully on an unrecognised version
# rather than fail to render.
DECISION_TRACE_VERSION = 1

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class DecisionTraceEntry:
    """One named indicator/value that contributed to a decision.

    Attributes:
        name: Short, stable identifier for the indicator (e.g.
            ``"rsi_14"``). Keep it stable across runs of the same
            strategy so external tooling can track it over time.
        value: The indicator's value at decision time. Must be a
            JSON scalar (str, int, float, bool, or None).
        unit: Optional unit label (e.g. ``"%"``, ``"EUR"``).
        description: Optional human-readable explanation.
        group: Optional grouping label (e.g. ``"trend"``,
            ``"momentum"``) a renderer may use to cluster related
            entries. Purely cosmetic — omit it and every entry
            renders as one flat table.
    """

    name: str
    value: Union[str, int, float, bool, None]
    unit: Optional[str] = None
    description: Optional[str] = None
    group: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError(
                f"DecisionTraceEntry.name must be a non-empty str, "
                f"got {self.name!r}"
            )
        if not isinstance(self.value, _JSON_SCALAR_TYPES):
            raise ValueError(
                f"DecisionTraceEntry.value for {self.name!r} must be a JSON "
                f"scalar (str, int, float, bool or None), got "
                f"{type(self.value).__name__}. Convert indicator/array "
                f"values (e.g. the latest row of a Series) to a plain "
                f"value before adding them to a DecisionTrace."
            )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "description": self.description,
            "group": self.group,
        }

    @staticmethod
    def from_dict(data: dict) -> "DecisionTraceEntry":
        return DecisionTraceEntry(
            name=data["name"],
            value=data.get("value"),
            unit=data.get("unit"),
            description=data.get("description"),
            group=data.get("group"),
        )


@dataclass(frozen=True)
class DecisionTrace:
    """A portable, versioned explanation for one signal decision.

    Attach it to a :class:`Signal` via
    :py:meth:`Signal.with_decision_trace`, which stores it under the
    reserved ``metadata["decision_trace"]`` key
    (:data:`DECISION_TRACE_METADATA_KEY`). Because ``Signal.metadata``
    already flows into ``Order.metadata`` when a signal is executed,
    and every signal — approved or rejected — is captured in
    ``RunReport.signals``, a decision trace explains a decision whether
    or not it ever became an order.

    Example:
        >>> from investing_algorithm_framework import (
        ...     DecisionTrace, DecisionTraceEntry, Signal, SignalSide,
        ... )
        >>> trace = DecisionTrace(
        ...     summary="RSI oversold and price above the 200d SMA",
        ...     entries=[
        ...         DecisionTraceEntry("rsi_14", 28.4),
        ...         DecisionTraceEntry("close", 41500.0, unit="EUR"),
        ...         DecisionTraceEntry("sma_200", 41230.5, unit="EUR"),
        ...     ],
        ... )
        >>> signal = Signal(
        ...     symbol="BTC", side=SignalSide.OPEN_LONG,
        ... ).with_decision_trace(trace)
    """

    entries: List[DecisionTraceEntry] = field(default_factory=list)
    summary: Optional[str] = None
    version: int = DECISION_TRACE_VERSION

    def to_dict(self) -> dict:
        return {
            "decision_trace_version": self.version,
            "score_card_version": self.version,
            "summary": self.summary,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @staticmethod
    def from_dict(data: dict) -> "DecisionTrace":
        return DecisionTrace(
            entries=[
                DecisionTraceEntry.from_dict(entry)
                for entry in data.get("entries", [])
            ],
            summary=data.get("summary"),
            version=data.get(
                "decision_trace_version",
                data.get("score_card_version", DECISION_TRACE_VERSION),
            ),
        )

    @staticmethod
    def from_confluence_result(
        result: Any,
        indicator_snapshot: Optional[Mapping[str, Any]] = None,
    ) -> "DecisionTrace":
        """Flatten a confluence result into the existing audit format."""
        entries = [
            DecisionTraceEntry("decision", result.decision, group="decision"),
            DecisionTraceEntry("score", result.score, group="decision"),
            DecisionTraceEntry(
                "minimum_score", result.minimum_score, group="decision"
            ),
            DecisionTraceEntry(
                "primary_triggered",
                result.primary_triggered,
                group="decision",
            ),
            DecisionTraceEntry(
                "requirements_passed",
                result.requirements_passed,
                group="decision",
            ),
            DecisionTraceEntry(
                "veto_triggered", result.veto_triggered, group="decision"
            ),
        ]
        for group in result.groups:
            for name in (
                "score", "matches", "minimum_score", "minimum_matches",
                "passed",
            ):
                value = getattr(group, name)
                if value is not None:
                    entries.append(DecisionTraceEntry(
                        name=name,
                        value=value,
                        description=f"{group.category} group {name}",
                        group=group.name,
                    ))
        for evaluation in result.evaluations:
            description = evaluation.category
            if evaluation.category == "score":
                description = f"score contribution: {evaluation.points:+g}"
            entries.append(DecisionTraceEntry(
                name=evaluation.name,
                value=evaluation.matched,
                description=description,
                group=evaluation.group or evaluation.category,
            ))
        if indicator_snapshot is not None:
            snapshot = (
                indicator_snapshot
                if isinstance(indicator_snapshot, Mapping)
                else indicator_snapshot.values
            )
            for name, value in snapshot.items():
                if hasattr(value, "item"):
                    value = value.item()
                entries.append(DecisionTraceEntry(
                    name=name,
                    value=value,
                    description="indicator snapshot",
                    group="indicators",
                ))
        return DecisionTrace(
            entries=entries,
            summary=(
                f"{result.card_name}: {result.decision} "
                f"({result.score:g} / {result.minimum_score:g})"
            ),
        )

    @staticmethod
    def of(
        *entries: DecisionTraceEntry, summary: Optional[str] = None
    ) -> "DecisionTrace":
        """Construct a trace from one or more entries."""
        return DecisionTrace(entries=list(entries), summary=summary)


# Backward-compatible aliases for persisted integrations and user strategies.
ScoreCard = DecisionTrace
ScoreCardEntry = DecisionTraceEntry
SCORE_CARD_METADATA_KEY = "score_card"
SCORE_CARD_VERSION = DECISION_TRACE_VERSION


def normalize_trace_metadata(metadata: Mapping[str, Any]) -> dict:
    """Expose both metadata keys, preferring an explicit canonical value."""
    normalized = dict(metadata)
    if DECISION_TRACE_METADATA_KEY in normalized:
        trace = normalized[DECISION_TRACE_METADATA_KEY]
    elif SCORE_CARD_METADATA_KEY in normalized:
        trace = normalized[SCORE_CARD_METADATA_KEY]
    else:
        return normalized
    if isinstance(trace, Mapping):
        trace = dict(trace)
        version = trace.get(
            "decision_trace_version",
            trace.get("score_card_version", DECISION_TRACE_VERSION),
        )
        trace["decision_trace_version"] = version
        trace["score_card_version"] = version
    normalized[DECISION_TRACE_METADATA_KEY] = trace
    normalized[SCORE_CARD_METADATA_KEY] = trace
    return normalized
