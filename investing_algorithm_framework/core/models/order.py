from sqlalchemy import Column, DateTime, String, Boolean, Float, Integer
from datetime import datetime
from investing_algorithm_framework.core.models import db
from .order_type import OrderType


class Order(db.Model):
    # Integer id for the Order as the primary key
    id = Column(Integer, primary_key=True)

    # order type (sell/buy)
    order_type = Column(String)

    # Asset Symbol (e.g. BTCEUR)
    symbol = Column(String)

    # Set to true, if order is completed at Binance platform
    completed = Column(Boolean, default=False)

    # The price of the asset
    price = Column(Float)
    total_price = Column(Float)
    commission = Column(Float)

    # Portfolio attributes
    amount = Column(Integer)

    # Date Time of creation
    created_at = Column(DateTime, default=datetime.now())
    
    def __init__(self, order_type, **kwargs):
        self.order_type = OrderType.from_string(order_type).value
        super(Order, self).__init__(**kwargs)
