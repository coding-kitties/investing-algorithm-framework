from sqlalchemy import Column, String, Float, Integer
from sqlalchemy.orm import relationship
from investing_algorithm_framework.core.models import db


class Position(db.Model):
    # Integer id for the Order as the primary key
    id = Column(Integer, primary_key=True)

    # Asset Symbol (e.g. BTC)
    symbol = Column(String, unique=True)

    # The price of the asset
    orders = relationship(
        "Order", back_populates="position", cascade="all, delete-orphan"
    )
    amount = Column(Float)

    def __init__(self, symbol):
        self.symbol = symbol
