from sqlalchemy import Column, DateTime, String, Boolean, Float, Integer, \
    ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.core.exceptions import OperationalException
from .order_type import OrderType


class Order(db.Model):
    # Integer id for the Order as the primary key
    id = Column(Integer, primary_key=True)

    # order type (sell/buy)
    order_type = Column(String)

    # broker
    broker = Column(String)

    first_symbol = Column(String)
    second_symbol = Column(String)

    # Set to true, if order is completed at Binance platform
    completed = Column(Boolean, default=False)
    terminated = Column(Boolean, default=False)

    # The price of the asset
    price = Column(Float)
    amount = Column(Float)
    commission = Column(Float)

    # Portfolio attributes
    total_price = Column(Integer)
    # Date Time of creation
    created_at = Column(DateTime, default=datetime.now())

    position_id = Column(Integer, ForeignKey('position.id'))
    position = relationship("Position", back_populates="orders")

    def __init__(self, order_type, trading_pair, price, amount, **kwargs):
        self.order_type = OrderType.from_string(order_type).value

        if "/" in trading_pair:
            pairs = trading_pair.split("/")
        else:
            pairs = trading_pair.split("-")

        if len(pairs) != 2:
            raise OperationalException("Trading pair format is not supported")

        self.first_symbol = pairs[0]
        self.second_symbol = pairs[1]

        self.price = price
        self.amount = amount
        self.total_price = self.amount * self.price
        super(Order, self).__init__(**kwargs)
