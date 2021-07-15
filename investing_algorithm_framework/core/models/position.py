from sqlalchemy import UniqueConstraint, event
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.core.models import db, OrderSide
from investing_algorithm_framework.core.models.model_extension \
    import ModelExtension


class Position(db.Model, ModelExtension):
    __tablename__ = "positions"

    # Integer id for the Order as the primary key
    id = db.Column(db.Integer, primary_key=True)

    # Asset Symbol (e.g. BTC)
    symbol = db.Column(db.String)

    # The price of the asset
    orders = relationship(
        "Order", back_populates="position", cascade="all, delete-orphan"
    )

    amount = db.Column(db.Float)

    # Relationships
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'))
    portfolio = relationship("Portfolio", back_populates="positions")

    # Constraints
    __table_args__ = (
        UniqueConstraint('symbol', 'portfolio_id', name='_symbol_broker_uc'),
    )

    def __init__(self, symbol):
        self.symbol = symbol
        self.amount = 0

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    def __repr__(self):
        return self.repr(
            id=self.id,
            symbol=self.symbol,
            amount=self.amount,
        )


@event.listens_for(Position.orders, 'append')
def parent_child_relation_inserted(position, order, target):

    if OrderSide.SELL.equals(order.order_side):
        position.amount -= order.amount
    else:
        position.amount += order.amount
