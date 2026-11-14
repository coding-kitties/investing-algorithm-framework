from copy import deepcopy
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from uuid import uuid4

from investing_algorithm_framework.domain.config import Environment
from investing_algorithm_framework.domain.models.base_model import BaseModel
from .decision_trace import normalize_trace_metadata


def _normalize_decision_traces(records):
    normalized = []
    for record in records or []:
        if "decision_trace" in record or "score_card" in record:
            normalized.append(normalize_trace_metadata(record))
        else:
            normalized.append(normalize_trace_metadata({
                "decision_trace": record,
            })["decision_trace"])
    return normalize_report_value(normalized)


def _normalize_metadata_records(records):
    return [
        {**record, "metadata": normalize_trace_metadata(record["metadata"])}
        if isinstance(record.get("metadata"), dict) else dict(record)
        for record in records or []
    ]


def _normalize_signal_reports(reports):
    records = _normalize_metadata_records(reports)
    if any("signals" in record for record in records):
        raise ValueError("RunReport.signals requires flat signal entries")
    return normalize_report_value(records)


def normalize_report_value(value):
    """Detach report data and normalize nested values for strict JSON."""
    if isinstance(value, Enum):
        return normalize_report_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Run report object keys must be strings")
        return {
            key: normalize_report_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_report_value(item) for item in value]
    if hasattr(value, "item"):
        return normalize_report_value(value.item())
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    raise TypeError(f"Unsupported run report value: {type(value).__name__}")


def _normalize_indicators(records):
    normalized = deepcopy(list(records)) if records is not None else []
    for record in normalized:
        value = record["value"]
        if hasattr(value, "item"):
            value = value.item()
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise TypeError("Indicator values must be JSON scalars")
        record["value"] = (
            None if isinstance(value, float) and not isfinite(value)
            else value
        )
        timestamp = record.get("timestamp")
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            record["timestamp"] = (
                timestamp.astimezone(timezone.utc).isoformat()
            )
    return normalized


def create_run_report_id(algorithm_id, started_at):
    timestamp = started_at
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    return f"{algorithm_id or 'unassigned'}_{timestamp}_{uuid4().hex}"


class RunReport(BaseModel):
    """Persisted outcome of a bounded invocation or continuous execution tick.

    No-signal strategy executions are completed runs. Failed and skipped
    executions carry explicit outcomes rather than reusing an earlier report.

    Attributes:
        id: Execution identifier: algorithm id, UTC start time and unique
            suffix.
            Assigned to transient reports as well as persisted reports.
        strategy_ids: Sorted identifiers of strategies covered by this run.
        status: "completed", "algorithm_disabled", "execution_error",
            "interrupted", "no_strategy_due", or "loop_stopped".
        error: Error text for a failed execution, otherwise None.
        algorithm_id: The id of the algorithm that produced this run,
            so reports from multiple bots sharing one database can be
            told apart.
        environment: "PROD", "PAPER", "TEST", or "BACKTEST".
        number_of_iterations: The bounded iteration count passed to
            ``App.run()`` for this invocation.
        started_at: When this invocation began.
        completed_at: When this invocation finished, including failure/skip.
        orders: Orders created during this run, most-recent last. Each
            order dict already carries its own ``strategy_id``.
            Includes new orders, orders whose status changed this run
            (e.g. filled/canceled), and any order still pending at the
            venue regardless of when it was created — a still-open
            limit order keeps appearing in every report until it
            finally resolves.
        signals: Flat per-signal outcomes — every signal
            the strategy emitted this run, whether it turned into an
            order ("approved") or was dropped ("rejected", with the
            reason from the phase pipeline that dropped it). Each
            entry carries its own strategy_id and evaluation timestamp.
            Cooldown rejections may include reason_details with the configured
            cooldown_bars and remaining_bars at the actual blocking gate.
        confluence_scores: Every evaluated confluence card, including
            warm-up, rejected and no-signal evaluations, with strategy_id,
            symbol, timestamp, card_id, side, groups and rule evaluations.
        data_sources: Latest completed source row per strategy/tick, with
            identifier, symbol, data_type, time_frame, evaluation timestamp,
            source_timestamp and values. Empty sources have no row timestamp
            and an empty values object. Full input windows are not stored.
        positions: All current positions across configured portfolios.
        portfolios: All current portfolios.
        trades: All current trades across configured portfolios. Each
            trade dict already carries its own ``strategy_id``.
        indicators: Evaluated outputs and explicitly recorded indicator
            trace entries, independent of signals. Each entry contains
            strategy_id, symbol, timestamp, name and a JSON scalar value.
            Unavailable/non-finite values are None.
        decision_traces: Every ``DecisionTrace`` recorded this run via
            ``TradingStrategy.record_decision_trace``, flattened across
            all strategies/ticks into one top-level list — one entry
            per recording, each carrying its own ``strategy_id``,
            ``symbol``, ``summary``, and ``entries``. Present even for
            a tick where no signal/order was produced at all, so a
            caller can see *why* nothing happened.
    """

    def __init__(
        self,
        id=None,
        algorithm_id=None,
        environment=None,
        number_of_iterations=None,
        started_at=None,
        completed_at=None,
        orders=None,
        signals=None,
        positions=None,
        portfolios=None,
        trades=None,
        score_cards=None,
        decision_traces=None,
        status="completed",
        error=None,
        strategy_ids=None,
        indicators=None,
        confluence_scores=None,
        data_sources=None,
        stop_losses=None,
        take_profits=None,
    ):
        self.id = (
            id if isinstance(id, str) and id
            else create_run_report_id(algorithm_id, started_at)
        )
        self.status = status
        self.error = error
        self.algorithm_id = algorithm_id
        self.environment = (
            environment.value if isinstance(environment, Environment)
            else environment
        )
        self.number_of_iterations = number_of_iterations
        self.started_at = started_at
        self.completed_at = completed_at
        self.orders = _normalize_metadata_records(orders)
        self.signals = _normalize_signal_reports(signals)
        self.positions = positions if positions is not None else []
        self.portfolios = portfolios if portfolios is not None else []
        self.trades = _normalize_metadata_records(trades)
        self.indicators = _normalize_indicators(indicators)
        self.confluence_scores = normalize_report_value(
            confluence_scores if confluence_scores is not None else []
        )
        self.data_sources = normalize_report_value(
            data_sources if data_sources is not None else []
        )
        self.decision_traces = _normalize_decision_traces(
            decision_traces if decision_traces is not None else score_cards
        )
        self.stop_losses = normalize_report_value(stop_losses or [])
        self.take_profits = normalize_report_value(take_profits or [])
        self.strategy_ids = sorted({
            strategy_id
            for strategy_id in (
                strategy_ids if strategy_ids is not None else [
                    record.get("strategy_id")
                    for records in (
                        self.signals, self.orders, self.trades,
                        self.decision_traces, self.indicators,
                        self.confluence_scores, self.data_sources,
                        self.stop_losses, self.take_profits,
                    )
                    for record in records
                ]
            )
            if strategy_id is not None
        })

    @property
    def score_cards(self):
        """Compatibility alias for :attr:`decision_traces`."""
        return self.decision_traces

    @score_cards.setter
    def score_cards(self, value):
        self.decision_traces = _normalize_decision_traces(value)

    def to_dict(self):
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value

        return {
            "id": self.id,
            "status": self.status or "completed",
            "error": self.error,
            "algorithm_id": self.algorithm_id,
            "strategy_ids": list(self.strategy_ids),
            "environment": self.environment,
            "number_of_iterations": self.number_of_iterations,
            "started_at": ensure_iso(self.started_at),
            "completed_at": ensure_iso(self.completed_at),
            "orders": _normalize_metadata_records(self.orders),
            "signals": _normalize_signal_reports(self.signals),
            "stop_losses": normalize_report_value(self.stop_losses),
            "take_profits": normalize_report_value(self.take_profits),
            "indicators": _normalize_indicators(self.indicators),
            "confluence_scores": normalize_report_value(
                self.confluence_scores,
            ),
            "data_sources": normalize_report_value(self.data_sources),
            "positions": self.positions,
            "portfolios": self.portfolios,
            "trades": _normalize_metadata_records(self.trades),
            "decision_traces": _normalize_decision_traces(
                self.decision_traces
            ),
            "score_cards": _normalize_decision_traces(self.decision_traces),
        }

    @staticmethod
    def from_dict(data: dict):
        return RunReport(
            id=data.get("id"),
            status=data.get("status", "completed"),
            error=data.get("error"),
            algorithm_id=data.get("algorithm_id"),
            strategy_ids=data.get("strategy_ids"),
            environment=data.get("environment"),
            number_of_iterations=data.get("number_of_iterations"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            orders=data.get("orders"),
            signals=data.get("signals"),
            stop_losses=data.get("stop_losses"),
            take_profits=data.get("take_profits"),
            indicators=data.get("indicators"),
            confluence_scores=data.get("confluence_scores"),
            data_sources=data.get("data_sources"),
            positions=data.get("positions"),
            portfolios=data.get("portfolios"),
            trades=data.get("trades"),
            score_cards=data.get("score_cards"),
            decision_traces=data.get("decision_traces"),
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            algorithm_id=self.algorithm_id,
            completed_at=self.completed_at,
        )
