"""ScoreCard — a small, versioned, cross-platform explanation object.

A :class:`ScoreCard` answers "why did this signal fire (or not)?" in
a shape that is useful to more than just this framework: any
dashboard, notebook, or hosting platform that reads a persisted
:class:`~investing_algorithm_framework.domain.models.run_report.RunReport`
should be able to render it without any strategy-specific code.

Design goals (why it looks the way it does):

* **Flat, not nested.** A :class:`ScoreCard` is just an optional
  ``summary`` string plus a flat list of :class:`ScoreCardEntry`
  (``name``/``value``/``unit``/``description``/optional ``group``).
  A flat list of rows renders as a table in any UI without the
  renderer needing to understand a strategy-specific tree shape.
* **JSON scalars only.** Every ``value`` must be a ``str``, ``int``,
  ``float``, ``bool``, or ``None`` — never a Series, array, or custom
  object — so a score card always survives a JSON round trip
  (HTTP response body, message queue, database column) unchanged.
* **Versioned.** ``score_card_version`` lets an independent consumer
  detect a shape it doesn't understand yet and skip/degrade
  gracefully instead of guessing or crashing.
* **Opt-in, additive.** Nothing about this object is required; a
  strategy that never builds one behaves exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

# Every platform/tool that wants to render a score card without
# strategy-specific code should look for this key on a Signal's
# ``metadata`` — and, for a signal that was executed, on the
# resulting Order's ``metadata`` (``Signal.metadata`` flows into
# ``Order.metadata`` verbatim; see ``Signal.with_score_card``).
SCORE_CARD_METADATA_KEY = "score_card"

# Bump only on breaking shape changes. Consumers should ignore
# unknown fields and degrade gracefully on an unrecognised version
# rather than fail to render.
SCORE_CARD_VERSION = 1

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class ScoreCardEntry:
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
                f"ScoreCardEntry.name must be a non-empty str, "
                f"got {self.name!r}"
            )
        if not isinstance(self.value, _JSON_SCALAR_TYPES):
            raise ValueError(
                f"ScoreCardEntry.value for {self.name!r} must be a JSON "
                f"scalar (str, int, float, bool or None), got "
                f"{type(self.value).__name__}. Convert indicator/array "
                f"values (e.g. the latest row of a Series) to a plain "
                f"value before adding them to a ScoreCard."
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
    def from_dict(data: dict) -> "ScoreCardEntry":
        return ScoreCardEntry(
            name=data["name"],
            value=data.get("value"),
            unit=data.get("unit"),
            description=data.get("description"),
            group=data.get("group"),
        )


@dataclass(frozen=True)
class ScoreCard:
    """A portable, versioned explanation for one signal decision.

    Attach it to a :class:`Signal` via
    :py:meth:`Signal.with_score_card`, which stores it under the
    reserved ``metadata["score_card"]`` key
    (:data:`SCORE_CARD_METADATA_KEY`). Because ``Signal.metadata``
    already flows into ``Order.metadata`` when a signal is executed,
    and every signal — approved or rejected — is captured in
    ``RunReport.signals``, a score card explains a decision whether
    or not it ever became an order.

    Example:
        >>> from investing_algorithm_framework import (
        ...     ScoreCard, ScoreCardEntry, Signal, SignalSide,
        ... )
        >>> card = ScoreCard(
        ...     summary="RSI oversold and price above the 200d SMA",
        ...     entries=[
        ...         ScoreCardEntry("rsi_14", 28.4),
        ...         ScoreCardEntry("close", 41500.0, unit="EUR"),
        ...         ScoreCardEntry("sma_200", 41230.5, unit="EUR"),
        ...     ],
        ... )
        >>> signal = Signal(
        ...     symbol="BTC", side=SignalSide.OPEN_LONG,
        ... ).with_score_card(card)
    """

    entries: List[ScoreCardEntry] = field(default_factory=list)
    summary: Optional[str] = None
    version: int = SCORE_CARD_VERSION

    def to_dict(self) -> dict:
        return {
            "score_card_version": self.version,
            "summary": self.summary,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @staticmethod
    def from_dict(data: dict) -> "ScoreCard":
        return ScoreCard(
            entries=[
                ScoreCardEntry.from_dict(entry)
                for entry in data.get("entries", [])
            ],
            summary=data.get("summary"),
            version=data.get("score_card_version", SCORE_CARD_VERSION),
        )

    @staticmethod
    def of(
        *entries: ScoreCardEntry, summary: Optional[str] = None
    ) -> "ScoreCard":
        """Convenience constructor: ``ScoreCard.of(entry1, entry2, ...)``."""
        return ScoreCard(entries=list(entries), summary=summary)
