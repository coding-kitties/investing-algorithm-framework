"""Version 1 language-neutral evidence records, not a recording sink."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from hashlib import sha256
import json
from math import isfinite
import struct
from typing import Any

from investing_algorithm_framework.domain.models.confluence import (
    ConfluenceCard, ConfluenceResult, GroupEvaluation, RuleEvaluation,
)
from investing_algorithm_framework.domain.models.decision_trace import (
    DecisionTrace, DecisionTraceEntry,
)


RECORD_VERSION = 1


def canonical_bytes(value: Any) -> bytes:
    """Encode the typed canonical JSON profile specified in the record spec."""
    def encode(item):
        if item is None:
            return ["null"]
        if type(item) is bool:
            return ["bool", item]
        if type(item) is int:
            if not -(2 ** 63) <= item < 2 ** 63:
                raise ValueError("Canonical integers must fit int64")
            return ["int", str(item)]
        if type(item) is float:
            if not isfinite(item):
                raise ValueError("Canonical floats must be finite")
            return ["float", struct.pack(">d", item).hex()]
        if type(item) is str:
            item.encode("utf-8")
            return ["str", item]
        if isinstance(item, (list, tuple)):
            return ["list", [encode(child) for child in item]]
        if isinstance(item, dict) and all(
            type(key) is str for key in item
        ):
            return ["map", [[key, encode(item[key])] for key in sorted(item)]]
        raise TypeError(f"Unsupported canonical value: {type(item).__name__}")

    return json.dumps(encode(value), ensure_ascii=True,
                      separators=(",", ":")).encode("ascii")


def content_id(kind: str, value: Any) -> str:
    """Domain-separated SHA-256 ID; kind is an ASCII schema identifier."""
    if not kind or not all(
        char in "abcdefghijklmnopqrstuvwxyz_" for char in kind
    ):
        raise ValueError("Invalid content ID kind")
    digest = sha256(
        f"iaf-records:1:{kind}\n".encode("ascii") + canonical_bytes(value)
    ).hexdigest()
    return f"{kind}:sha256:{digest}"


def timestamp_us(value: datetime) -> int:
    """Convert an aware datetime without a lossy floating-point timestamp."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required")
    delta = value.astimezone(timezone.utc) - datetime(
        1970, 1, 1, tzinfo=timezone.utc
    )
    return ((delta.days * 86400 + delta.seconds) * 1_000_000
            + delta.microseconds)


def pack_bits(values) -> bytes:
    """Pack any rule count, least-significant bit first in each byte."""
    values = tuple(values)
    packed = bytearray((len(values) + 7) // 8)
    for index, value in enumerate(values):
        if type(value) is not bool:
            raise ValueError("Bit values must be bool")
        if value:
            packed[index // 8] |= 1 << (index % 8)
    return bytes(packed)


def unpack_bits(packed: bytes, count: int) -> tuple[bool, ...]:
    """Validate length and zero padding before decoding a bit vector."""
    if type(count) is not int or count < 0 or not isinstance(packed, bytes):
        raise ValueError("Invalid bit vector")
    if len(packed) != (count + 7) // 8:
        raise ValueError("Bit vector length does not match rule count")
    if count % 8 and packed[-1] >> (count % 8):
        raise ValueError("Bit vector padding must be zero")
    return tuple(bool(packed[index // 8] & (1 << (index % 8)))
                 for index in range(count))


def decode_canonical(payload: bytes) -> Any:
    """Decode canonical bytes, rejecting noncanonical or malformed input."""
    def decode(node):
        tag = node[0]
        if tag == "null":
            return None
        if tag in ("bool", "str"):
            return node[1]
        if tag == "int":
            return int(node[1])
        if tag == "float":
            return struct.unpack(">d", bytes.fromhex(node[1]))[0]
        if tag == "list":
            return [decode(child) for child in node[1]]
        if tag == "map":
            return {key: decode(child) for key, child in node[1]}
        raise ValueError("Unknown canonical type")

    try:
        value = decode(json.loads(payload))
        if canonical_bytes(value) != payload:
            raise ValueError("Noncanonical payload")
        return value
    except (IndexError, KeyError, TypeError, struct.error) as error:
        raise ValueError("Malformed canonical payload") from error


class Outcome(IntEnum):
    FALSE = 0
    TRUE = 1
    SKIPPED = 2
    UNAVAILABLE = 3


@dataclass(frozen=True)
class RuleSlot:
    path: str
    name: str
    category: str
    group: str | None = None
    points: float = 0.0
    score_type: Any = None


@dataclass(frozen=True)
class CardDefinition:
    """Immutable canonical definition, independent of the producer engine."""

    payload: bytes

    def __post_init__(self):
        data = decode_canonical(self.payload)
        if not isinstance(data, dict) or (
            type(data.get("confluence_card_version")) is not int
            or data["confluence_card_version"] != 1
        ):
            raise ValueError("Unsupported confluence definition version")
        card = ConfluenceCard.from_dict(data)
        if canonical_bytes(card.to_dict()) != self.payload:
            raise ValueError("Definition is not a complete v1 card")

    @classmethod
    def from_card(cls, card: ConfluenceCard) -> CardDefinition:
        return cls(canonical_bytes(card.to_dict()))

    @property
    def card_id(self) -> str:
        return content_id("card", decode_canonical(self.payload))

    def to_card(self) -> ConfluenceCard:
        return ConfluenceCard.from_dict(decode_canonical(self.payload))

    def slots(self) -> tuple[RuleSlot, ...]:
        card = self.to_card()
        slots = []

        def scoring(rules, prefix, group=None):
            for index, rule in enumerate(rules):
                slots.append(RuleSlot(
                    f"{prefix}/{index}", rule.name, "score",
                    rule.group or group, float(rule.points), rule.score_type,
                ))

        for index, rule in enumerate(card.requirements):
            slots.append(RuleSlot(f"requirements/{index}", rule.name,
                                  "requirement"))
        scoring(card.primary.rules, "primary/rules", card.primary.name)
        slots.append(RuleSlot("primary", card.primary.name, "primary"))
        for index, rule in enumerate(card.vetoes):
            slots.append(RuleSlot(f"vetoes/{index}", rule.name, "veto"))
        for index, group in enumerate(card.secondary):
            scoring(group.rules, f"secondary/{index}/rules", group.name)
        scoring(card.scoring, "scoring")
        return tuple(slots)

    def rule_id(self, index: int) -> str:
        return f"{self.card_id}#{self.slots()[index].path}"


def evaluation_id(attempt_id: str, sequence: int) -> str:
    if not attempt_id or type(sequence) is not int or (
        not 0 <= sequence < 2**63
    ):
        raise ValueError("Evaluation needs an attempt ID and int64 sequence")
    return content_id("evaluation", [attempt_id, sequence])


@dataclass(frozen=True)
class ConfluenceEvaluation:
    """Compact evidence referencing names and expressions by definition."""

    attempt_id: str
    sequence: int
    timestamp_us: int
    symbol_id: str
    strategy_id: str
    card_id: str
    score: float | None
    qualified: bool | None
    outcomes: bytes
    group_scores: tuple[float | None, ...] = ()
    detail_id: str | None = None

    def __post_init__(self):
        evaluation_id(self.attempt_id, self.sequence)
        if type(self.timestamp_us) is not int or not (
            -(2**63) <= self.timestamp_us < 2**63
        ):
            raise ValueError("timestamp_us must fit int64")
        if not self.symbol_id or not self.card_id or not self.strategy_id:
            raise ValueError("Symbol, strategy and definition IDs required")
        if not isinstance(self.outcomes, bytes) or any(
            value not in tuple(Outcome) for value in self.outcomes
        ):
            raise ValueError("Invalid outcome codes")
        if self.qualified is not None and type(self.qualified) is not bool:
            raise ValueError("qualified must be bool or null")
        for score in (self.score, *self.group_scores):
            if score is not None and (
                type(score) not in (int, float) or not isfinite(score)
            ):
                raise ValueError("Scores must be finite or null")
        incomplete = any(value >= Outcome.SKIPPED for value in self.outcomes)
        if incomplete and (
            self.score is not None or self.qualified is not None
        ):
            raise ValueError("Incomplete evaluations have null totals")
        if not incomplete and (self.score is None or self.qualified is None):
            raise ValueError("Complete evaluations require totals")

    @property
    def evaluation_id(self) -> str:
        return evaluation_id(self.attempt_id, self.sequence)

    @classmethod
    def from_result(
        cls, definition: CardDefinition, result: ConfluenceResult, *,
        attempt_id: str, sequence: int, timestamp: datetime, symbol_id: str,
        strategy_id: str,
        detail_id: str | None = None,
    ) -> ConfluenceEvaluation:
        record = cls(
            attempt_id=attempt_id, sequence=sequence,
            timestamp_us=timestamp_us(timestamp), symbol_id=symbol_id,
            strategy_id=strategy_id,
            card_id=definition.card_id, score=result.score,
            qualified=bool(result.qualified),
            outcomes=bytes(int(bool(item.matched))
                           for item in result.evaluations),
            group_scores=tuple(group.score for group in result.groups),
            detail_id=detail_id,
        )
        if record.to_result(definition).to_dict() != result.to_dict():
            raise ValueError("Result does not match the supplied definition")
        return record

    def _validate_definition(self, definition):
        slots = definition.slots()
        card = definition.to_card()
        group_count = len(card.secondary) + int(
            card.primary.expression is None
        )
        if self.card_id != definition.card_id or (
            len(slots) != len(self.outcomes)
        ):
            raise ValueError("Evaluation references a different definition")
        if len(self.group_scores) != group_count:
            raise ValueError("Group score count does not match definition")
        return card, slots

    def to_result(self, definition: CardDefinition) -> ConfluenceResult:
        """Rebuild one complete result without evaluating any expressions."""
        card, slots = self._validate_definition(definition)
        if any(value >= Outcome.SKIPPED for value in self.outcomes):
            raise ValueError("Incomplete evidence is not a ConfluenceResult")
        evaluations = tuple(RuleEvaluation(
            name=slot.name, matched=bool(outcome), category=slot.category,
            points=slot.points if outcome else 0.0, group=slot.group,
            score_type=slot.score_type,
        ) for slot, outcome in zip(slots, self.outcomes))
        by_path = dict(zip((slot.path for slot in slots), self.outcomes))
        groups = []
        definitions = ([] if card.primary.expression is not None else [
            (card.primary, "primary", "primary/rules")
        ]) + [(group, "secondary", f"secondary/{index}/rules")
              for index, group in enumerate(card.secondary)]
        for (group, category, prefix), score in zip(
            definitions, self.group_scores
        ):
            if score is None:
                raise ValueError("Complete groups require scores")
            matches = sum(by_path[f"{prefix}/{index}"]
                          for index in range(len(group.rules)))
            groups.append(GroupEvaluation(
                name=group.name, category=category, matches=matches,
                score=score, minimum_matches=group.minimum_matches,
                minimum_score=group.minimum_score,
                passed=(matches >= group.minimum_matches and (
                    group.minimum_score is None or score >= group.minimum_score
                )),
            ))
        return ConfluenceResult(
            card_name=card.name, primary_triggered=bool(by_path["primary"]),
            requirements_passed=all(item.matched for item in evaluations
                                    if item.category == "requirement"),
            veto_triggered=any(item.matched for item in evaluations
                               if item.category == "veto"),
            score=self.score, minimum_score=float(card.minimum_score),
            qualified=self.qualified, evaluations=evaluations,
            groups=tuple(groups),
        )

    def to_trace(self, definition: CardDefinition, indicator_snapshot=None):
        """Materialize one explanation, including missing states."""
        card, slots = self._validate_definition(definition)
        if all(value < Outcome.SKIPPED for value in self.outcomes):
            return DecisionTrace.from_confluence_result(
                self.to_result(definition), indicator_snapshot
            )
        state = ("UNAVAILABLE" if Outcome.UNAVAILABLE in self.outcomes
                 else "SKIPPED")
        entries = [DecisionTraceEntry("decision", state, group="decision")]
        for slot, outcome in zip(slots, self.outcomes):
            entries.append(DecisionTraceEntry(
                slot.name,
                bool(outcome) if outcome < Outcome.SKIPPED else None,
                description=(
                    f"{slot.category}: {Outcome(outcome).name.lower()}"
                ),
                group=slot.group or slot.category,
            ))
        if indicator_snapshot is not None:
            entries.extend(DecisionTraceEntry(
                name, value, description="indicator snapshot",
                group="indicators",
            ) for name, value in indicator_snapshot.items())
        return DecisionTrace(entries=entries, summary=f"{card.name}: {state}")

    def to_record(self, definition: CardDefinition) -> dict:
        _, slots = self._validate_definition(definition)

        def bits(category):
            return pack_bits(outcome == Outcome.TRUE
                             for slot, outcome in zip(slots, self.outcomes)
                             if slot.category == category)

        return {
            "evaluation_id": self.evaluation_id,
            "attempt_id": self.attempt_id, "sequence": self.sequence,
            "timestamp_us": self.timestamp_us, "symbol_id": self.symbol_id,
            "strategy_id": self.strategy_id,
            "card_id": self.card_id, "score": self.score,
            "qualified": self.qualified,
            "primary_outcome": self.outcomes[
                next(index for index, slot in enumerate(slots)
                     if slot.category == "primary")
            ],
            "matched_rule_bits": bits("score"),
            "requirement_bits": bits("requirement"),
            "veto_bits": bits("veto"),
            "evaluated_bits": pack_bits(value != Outcome.SKIPPED
                                        for value in self.outcomes),
            "available_bits": pack_bits(value < Outcome.SKIPPED
                                        for value in self.outcomes),
            "group_scores": list(self.group_scores),
            "detail_id": self.detail_id,
        }

    @classmethod
    def from_record(cls, record: dict, definition: CardDefinition):
        slots = definition.slots()
        evaluated = unpack_bits(record["evaluated_bits"], len(slots))
        available = unpack_bits(record["available_bits"], len(slots))
        matches = {
            category: iter(unpack_bits(record[field], sum(
                slot.category == category for slot in slots
            )))
            for category, field in (
                ("score", "matched_rule_bits"),
                ("requirement", "requirement_bits"), ("veto", "veto_bits"),
            )
        }
        outcomes = []
        for slot, did_evaluate, is_available in zip(
            slots, evaluated, available
        ):
            matched = (record["primary_outcome"] == Outcome.TRUE
                       if slot.category == "primary"
                       else next(matches[slot.category]))
            outcomes.append(int(matched) if is_available else (
                Outcome.UNAVAILABLE if did_evaluate else Outcome.SKIPPED
            ))
        result = cls(
            **{key: record[key] for key in (
                "attempt_id", "sequence", "timestamp_us", "symbol_id",
                "strategy_id", "card_id", "score", "qualified", "detail_id",
            )}, outcomes=bytes(outcomes),
            group_scores=tuple(record["group_scores"]),
        )
        encoded = result.to_record(definition)
        if any(record[key] != value for key, value in encoded.items()):
            raise ValueError("Inconsistent evaluation bitsets or identity")
        return result


def encode_trace(trace: DecisionTrace) -> bytes:
    """Store generic traces without a card definition or legacy aliases."""
    payload = trace.to_dict()
    payload.pop("score_card_version")
    return canonical_bytes(payload)


def decode_trace(payload: bytes) -> DecisionTrace:
    data = decode_canonical(payload)
    if not isinstance(data, dict) or (
        type(data.get("decision_trace_version")) is not int
        or data["decision_trace_version"] != 1
    ):
        raise ValueError("Unsupported decision trace version")
    return DecisionTrace.from_dict(data)


def diagnostic_record(
    evaluation_id: str, *, indicator_snapshot=None,
    expression_outcomes=(), details=None,
) -> dict:
    """Encode optional ordered snapshots and expression-path outcomes."""
    snapshot = list((indicator_snapshot or {}).items())
    for name, value in snapshot:
        DecisionTraceEntry(name, value)
    outcomes = list(expression_outcomes)
    for path, outcome in outcomes:
        if not isinstance(path, str) or not path or (
            type(outcome) not in (int, Outcome)
            or outcome not in tuple(Outcome)
        ):
            raise ValueError("Invalid expression outcome")
    if len({path for path, _ in outcomes}) != len(outcomes):
        raise ValueError("Duplicate expression paths")
    document = {
        "version": RECORD_VERSION, "evaluation_id": evaluation_id,
        "indicator_snapshot": snapshot,
        "expression_outcomes": [(path, int(outcome))
                                for path, outcome in outcomes],
        "details": details,
    }
    return {
        "detail_id": content_id("detail", document),
        "evaluation_id": evaluation_id, "payload": canonical_bytes(document),
    }


def iter_decision_traces(records, load_definition, load_detail=None):
    """Decode on demand with only the current row/definition held in memory."""
    for row in records:
        if "trace_payload" in row:
            yield decode_trace(row["trace_payload"])
            continue
        definition = CardDefinition(load_definition(row["card_id"]))
        record = ConfluenceEvaluation.from_record(row, definition)
        snapshot = None
        if record.detail_id is not None:
            if load_detail is None:
                raise ValueError("A detail loader is required for this trace")
            document = decode_canonical(load_detail(record.detail_id))
            if content_id("detail", document) != record.detail_id or (
                document.get("evaluation_id") != record.evaluation_id
                or document.get("version") != RECORD_VERSION
            ):
                raise ValueError("Diagnostic identity mismatch")
            snapshot = dict(document["indicator_snapshot"])
        yield record.to_trace(definition, snapshot)
