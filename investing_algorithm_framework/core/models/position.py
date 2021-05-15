from sqlalchemy import Column, String, Float, Integer, event
from sqlalchemy.orm import relationship
from investing_algorithm_framework.core.models import db, OrderType


class Position(db.Model):
    # Integer id for the Order as the primary key
    id = Column(Integer, primary_key=True)

    # Asset Symbol (e.g. BTC)
    symbol = Column(String, unique=True)

    broker = Column(String)

    # The price of the asset
    orders = relationship(
        "Order", back_populates="position", cascade="all, delete-orphan"
    )
    amount = Column(Float)

    def __init__(self, symbol, broker):
        self.symbol = symbol
        self.broker = broker
        self.amount = 0


@event.listens_for(Position.orders, 'append')
def parent_child_relation_inserted(position, order, target):

    if OrderType.SELL.equals(order.order_type):
        position.amount += order.amount
    else:
        position.amount = position.amount - order.amount
