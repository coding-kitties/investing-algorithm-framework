from datetime import datetime

from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PositionCost
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPositionCost(SQLBaseModel, PositionCost, SQLAlchemyModelExtension):
    __tablename__ = "position_costs"
    id = Column(Integer, primary_key=True, unique=True)
    price = Column(Float)
    amount = Column(Float)
    created_at = Column(DateTime)
    position_id = Column(Integer, ForeignKey('positions.id'))
    position = relationship("SQLPosition", back_populates="position_costs")

    def __init__(
        self,
        price=0,
        amount=0,
        position_id=None,
        created_at=None,
    ):
        super(SQLPositionCost, self).__init__()
        self.amount = amount
        self.price = price
        self.position_id = position_id
        self.created_at = created_at
