import logging

from sqlalchemy import Column, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension

logger = logging.getLogger("investing_algorithm_framework")


class SQLOrderMetadata(SQLBaseModel, SQLAlchemyModelExtension):
    __tablename__ = "sql_order_metadata"
    id = Column(Integer, primary_key=True, unique=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    order = relationship('SQLOrder', back_populates='order_metadata')
    trade_id = Column(Integer)
    stop_loss_id = Column(Integer)
    take_profit_id = Column(Integer)
    amount = Column(Float)
    amount_pending = Column(Float)

    def __init__(
        self,
        order_id,
        amount,
        amount_pending,
        trade_id=None,
        stop_loss_id=None,
        take_profit_id=None,
    ):
        self.order_id = order_id
        self.trade_id = trade_id
        self.stop_loss_id = stop_loss_id
        self.take_profit_id = take_profit_id
        self.amount = amount
        self.amount_pending = amount_pending

    def __repr__(self):
        return f"<SQLOrderMetadata(id={self.id}, order_id={self.order_id}, " \
               f"trade_id={self.trade_id}, stop_loss_id={self.stop_loss_id}, "\
               f"take_profit_id={self.take_profit_id}, amount={self.amount}, "\
               f"amount_pending={self.amount_pending})>"
