"""Compatibility imports; use decision_trace for new integrations."""
from .decision_trace import (
    DecisionTrace, DecisionTraceEntry,
    DECISION_TRACE_METADATA_KEY, DECISION_TRACE_VERSION,
    ScoreCard, ScoreCardEntry, SCORE_CARD_METADATA_KEY, SCORE_CARD_VERSION,
)

__all__ = [
    "DecisionTrace", "DecisionTraceEntry",
    "DECISION_TRACE_METADATA_KEY", "DECISION_TRACE_VERSION",
    "ScoreCard", "ScoreCardEntry", "SCORE_CARD_METADATA_KEY",
    "SCORE_CARD_VERSION",
]
