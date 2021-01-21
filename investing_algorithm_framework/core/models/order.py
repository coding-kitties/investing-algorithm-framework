from sqlalchemy import Column, DateTime, String, Boolean, Float, Integer
from datetime import datetime


class Order:
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

    # Date Time of creation
    created_at = Column(DateTime, default=datetime.now())
