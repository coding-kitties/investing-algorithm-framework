import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import reconstructor, synonym

from investing_algorithm_framework.domain import RunReport
from investing_algorithm_framework.infrastructure.database import (
    SQLBaseModel
)
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


def utcnow():
    return datetime.now(tz=timezone.utc)


class SQLRunReport(RunReport, SQLBaseModel, SQLAlchemyModelExtension):
    """
    SQLRunReport model based on the RunReport domain model. The
    ``orders``/``signals``/``positions``/``portfolios``/``trades``
    lists are stored as JSON text columns, mirroring how ``SQLOrder``
    and ``SQLTrade`` persist their ``metadata`` dict.
    """
    __tablename__ = "run_reports"
    storage_id = Column("id", Integer, primary_key=True, unique=True)
    id = Column("report_id", String, unique=True, nullable=False)
    strategy_ids_json = Column(Text, default=None)
    algorithm_id = Column(String, default=None)
    status = Column(String, default="completed")
    error = Column(Text, default=None)
    environment = Column(String, default=None)
    number_of_iterations = Column(Integer, default=None)
    started_at = Column(DateTime(timezone=True), default=None)
    completed_at = Column(DateTime(timezone=True), default=utcnow)
    orders_json = Column(Text, default=None)
    signals_json = Column(Text, default=None)
    stop_losses_json = Column(Text, default=None)
    take_profits_json = Column(Text, default=None)
    indicators_json = Column(Text, default=None)
    confluence_scores_json = Column(Text, default=None)
    data_sources_json = Column(Text, default=None)
    positions_json = Column(Text, default=None)
    portfolios_json = Column(Text, default=None)
    trades_json = Column(Text, default=None)
    decision_traces_json = Column("score_cards_json", Text, default=None)
    score_cards_json = synonym("decision_traces_json")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sync_json_columns()

    def _sync_json_columns(self):
        payload = self.to_dict()
        self.strategy_ids_json = json.dumps(self.strategy_ids)
        self.orders_json = json.dumps(payload["orders"])
        self.signals_json = json.dumps(payload["signals"])
        self.stop_losses_json = json.dumps(payload["stop_losses"])
        self.take_profits_json = json.dumps(payload["take_profits"])
        self.indicators_json = json.dumps(payload["indicators"])
        self.confluence_scores_json = json.dumps(payload["confluence_scores"])
        self.data_sources_json = json.dumps(payload["data_sources"])
        self.positions_json = json.dumps(self.positions or [])
        self.portfolios_json = json.dumps(self.portfolios or [])
        self.trades_json = json.dumps(payload["trades"])
        self.decision_traces_json = json.dumps(payload["decision_traces"])

    @reconstructor
    def init_on_load(self):
        self.strategy_ids = json.loads(self.strategy_ids_json) \
            if self.strategy_ids_json else []
        self.orders = json.loads(self.orders_json) \
            if self.orders_json else []
        self.signals = json.loads(self.signals_json) \
            if self.signals_json else []
        self.indicators = json.loads(self.indicators_json) \
            if self.indicators_json else []
        self.confluence_scores = json.loads(self.confluence_scores_json) \
            if self.confluence_scores_json else []
        self.data_sources = json.loads(self.data_sources_json) \
            if self.data_sources_json else []
        self.positions = json.loads(self.positions_json) \
            if self.positions_json else []
        self.portfolios = json.loads(self.portfolios_json) \
            if self.portfolios_json else []
        self.trades = json.loads(self.trades_json) \
            if self.trades_json else []
        restored = RunReport(
            orders=self.orders, signals=self.signals, trades=self.trades,
            strategy_ids=self.strategy_ids or None,
            indicators=self.indicators,
            confluence_scores=self.confluence_scores,
            data_sources=self.data_sources,
            stop_losses=json.loads(self.stop_losses_json)
            if self.stop_losses_json else [],
            take_profits=json.loads(self.take_profits_json)
            if self.take_profits_json else [],
            decision_traces=json.loads(self.decision_traces_json)
            if self.decision_traces_json else [],
        )
        self.orders = restored.orders
        self.signals = restored.signals
        self.trades = restored.trades
        self.decision_traces = restored.decision_traces
        self.strategy_ids = restored.strategy_ids
        self.indicators = restored.indicators
        self.confluence_scores = restored.confluence_scores
        self.data_sources = restored.data_sources
        self.stop_losses = restored.stop_losses
        self.take_profits = restored.take_profits

    def update(self, data):
        data = dict(data)
        if "decision_traces" in data:
            data.pop("score_cards", None)
        json_fields = (
            "orders", "signals", "positions", "portfolios", "trades",
            "score_cards", "decision_traces", "indicators",
            "confluence_scores", "data_sources",
            "stop_losses", "take_profits",
        )
        for field_name in json_fields:
            if field_name in data:
                setattr(self, field_name, data.pop(field_name))
        super().update(data)
        self._sync_json_columns()
