from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import OrderFee
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLOrderFee(OrderFee, SQLBaseModel, SQLAlchemyModelExtension):
    __tablename__ = "order_fees"
    id = Column(Integer, primary_key=True, unique=True)
    currency = Column(String)
    cost = Column(Float)
    rate = Column(Float)
    order_id = Column(Integer, ForeignKey('orders.id'))
    order = relationship("SQLOrder", back_populates="fee")

    def __init__(self, currency, cost, rate, order_id):
        super().__init__(currency, cost, rate)
        self.order_id = order_id
