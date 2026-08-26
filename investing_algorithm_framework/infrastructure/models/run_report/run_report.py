import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import reconstructor

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
    id = Column(Integer, primary_key=True, unique=True)
    algorithm_id = Column(String, default=None)
    environment = Column(String, default=None)
    is_paper = Column(Boolean, default=None)
    number_of_iterations = Column(Integer, default=None)
    started_at = Column(DateTime(timezone=True), default=None)
    completed_at = Column(DateTime(timezone=True), default=utcnow)
    orders_json = Column(Text, default=None)
    signals_json = Column(Text, default=None)
    positions_json = Column(Text, default=None)
    portfolios_json = Column(Text, default=None)
    trades_json = Column(Text, default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sync_json_columns()

    def _sync_json_columns(self):
        self.orders_json = json.dumps(self.orders or [])
        self.signals_json = json.dumps(self.signals or [])
        self.positions_json = json.dumps(self.positions or [])
        self.portfolios_json = json.dumps(self.portfolios or [])
        self.trades_json = json.dumps(self.trades or [])

    @reconstructor
    def init_on_load(self):
        self.orders = json.loads(self.orders_json) \
            if self.orders_json else []
        self.signals = json.loads(self.signals_json) \
            if self.signals_json else []
        self.positions = json.loads(self.positions_json) \
            if self.positions_json else []
        self.portfolios = json.loads(self.portfolios_json) \
            if self.portfolios_json else []
        self.trades = json.loads(self.trades_json) \
            if self.trades_json else []

    def update(self, data):
        data = dict(data)
        json_fields = (
            "orders", "signals", "positions", "portfolios", "trades"
        )
        for field_name in json_fields:
            if field_name in data:
                setattr(self, field_name, data.pop(field_name))
        super().update(data)
        self._sync_json_columns()
