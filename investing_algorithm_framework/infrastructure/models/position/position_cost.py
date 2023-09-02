from sqlalchemy import Column, Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PositionCost
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.domain import parse_decimal_to_string


class SQLPositionCost(PositionCost, SQLBaseModel, SQLAlchemyModelExtension):
    __tablename__ = "position_costs"
    id = Column(Integer, primary_key=True, unique=True)
    price = Column(Numeric(precision=24, scale=20))
    amount = Column(Numeric(precision=24, scale=20))
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
        self.amount = parse_decimal_to_string(amount)
        self.price = parse_decimal_to_string(price)
        self.position_id = position_id
        self.created_at = created_at

    def update(self, data):

        if "price" in data:
            self.price = parse_decimal_to_string(data.pop("price"))

        if "amount" in data:
            self.amount = parse_decimal_to_string(data.pop("amount"))

        super(SQLPositionCost, self).update(data)
