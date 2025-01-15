from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import Trade
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLTrade(Trade, SQLBaseModel, SQLAlchemyModelExtension):
    """
    Trade model

    A trade is a combination of a buy and sell order that has been opened or
    closed.

    A trade is considered opened when a buy order is executed and there is
    no corresponding sell order. A trade is considered closed when a sell
    order is executed and the amount of the sell order is equal or larger
    to the amount of the buy order.

    A single sell order can close multiple buy orders. Also, a single
    buy order can be closed by multiple sell orders.

    Attributes:
    * buy_order: str, the id of the buy order
    * sell_orders: str, the id of the sell order
    * target_symbol: str, the target symbol of the trade
    * trading_symbol: str, the trading symbol of the trade
    * closed_at: datetime, the datetime when the trade was closed
    * remaining: float, the remaining amount of the trade
    * net_gain: float, the net gain of the trade
    * last_reported_price: float, the last reported price of the trade
    * created_at: datetime, the datetime when the trade was created
    * updated_at: datetime, the datetime when the trade was last updated
    """

    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, unique=True)
    # A one-to-one relationship for the buy order
    buy_order = relationship(
        'SQLOrder',
        primaryjoin="and_(SQLOrder.trade_id==SQLTrade.id, SQLOrder.order_side=='buy')",
        uselist=False
    )
    # A one-to-many relationship for the sell orders
    sell_orders = relationship(
        'SQLOrder',
        primaryjoin="and_(SQLOrder.trade_id==SQLTrade.id, SQLOrder.order_side=='sell')",
        uselist=True
    )
    target_symbol = Column(String)
    trading_symbol = Column(String)
    closed_at = Column(DateTime, default=None)
    amount = Column(Float, default=None)
    open_price = Column(Float, default=None)
    close_price = Column(Float, default=None)
    remaining = Column(Float, default=None)
    net_gain = Column(Float, default=0)
    last_reported_price = Column(Float, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    def __init__(
        self,
        buy_order_id,
        sell_order_ids,
        target_symbol,
        trading_symbol,
        closed_at,
        amount,
        remaining,
        net_gain,
        last_reported_price,
        created_at,
        updated_at,
    ):
        self.buy_order = buy_order_id
        self.sell_orders = sell_order_ids
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.closed_at = closed_at
        self.amount = amount
        self.remaining = remaining
        self.net_gain = net_gain
        self.last_reported_price = last_reported_price
        self.created_at = created_at
        self.updated_at = updated_at
