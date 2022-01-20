from abc import abstractmethod

from sqlalchemy.orm import relationship

from investing_algorithm_framework.core.models import db, OrderSide, \
    OrderStatus
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension


class PositionSnapshot:

    @abstractmethod
    def get_amount(self):
        pass

    @abstractmethod
    def get_cost(self):
        pass

    @abstractmethod
    def get_symbol(self):
        pass

    @staticmethod
    @abstractmethod
    def from_position(position):
        pass


class SQLLitePositionSnapshot(
    PositionSnapshot, db.Model, SQLAlchemyModelExtension
):
    __tablename__ = "position_snapshots"

    # Integer id for the Position as the primary key
    id = db.Column(db.Integer, primary_key=True)

    # Asset Symbol (e.g. BTC)
    symbol = db.Column(db.String)

    amount = db.Column(db.Float)
    cost = db.Column(db.Float)

    # Relationships
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio_snapshots.id'))
    portfolio = relationship("SQLLitePortfolioSnapshot", back_populates="positions")

    def __init__(self, symbol, amount, cost):
        self.symbol = symbol
        self.amount = amount
        self.cost = cost

    @staticmethod
    def from_position(position):
        orders = position.orders\
            .filter_by(
                order_side=OrderSide.BUY.value,
                status=OrderStatus.SUCCESS.value
            )\
            .all()

        cost = 0

        # Calculate the cost
        for order in orders:
            cost += order.amount_target_symbol * order.initial_price

        # Create an algorithm position snapshot
        return SQLLitePositionSnapshot(
            symbol=position.symbol,
            amount=position.amount,
            cost=cost
        )

    def get_amount(self):
        return self.amount

    def get_cost(self):
        return self.cost

    def get_symbol(self):
        return self.symbol

    def __repr__(self):
        return self.repr(
            id=self.id,
            symbol=self.symbol,
            amount=self.amount,
        )
