from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import Trade, TradeStatus
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.infrastructure.models\
    .order_trade_association import order_trade_association


class SQLTrade(Trade, SQLBaseModel, SQLAlchemyModelExtension):
    """
    SQL Trade model

    A trade is a combination of a buy and sell order that has been opened or
    closed.

    A trade is considered opened when a buy order is executed and there is
    no corresponding sell order. A trade is considered closed when a sell
    order is executed and the amount of the sell order is equal or larger
    to the amount of the buy order.

    A single sell order can close multiple buy orders. Also, a single
    buy order can be closed by multiple sell orders.

    Attributes:
    orders: str, the id of the buy order
        target_symbol: str, the target symbol of the trade
        trading_symbol: str, the trading symbol of the trade
        closed_at: datetime, the datetime when the trade was closed
        amount: float, the amount of the trade
        available_amount: float, the available amount of the trade
        remaining: float, the remaining amount that is not filled by the
            buy order that opened the trade.
        filled_amount: float, the filled amount of the trade by the buy
            order that opened the trade.
        net_gain: float, the net gain of the trade
        last_reported_price: float, the last reported price of the trade
        last_reported_price_datetime: datetime, the datetime when the last
            reported price was reported
        created_at: datetime, the datetime when the trade was created
        updated_at: datetime, the datetime when the trade was last updated
        status: str, the status of the trade
    """

    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, unique=True)
    orders = relationship(
        'SQLOrder',
        secondary=order_trade_association,
        back_populates='trades',
        lazy='joined'
    )
    target_symbol = Column(String)
    trading_symbol = Column(String)
    closed_at = Column(DateTime, default=None)
    opened_at = Column(DateTime, default=None)
    open_price = Column(Float, default=None)
    amount = Column(Float, default=None)
    available_amount = Column(Float, default=None)
    filled_amount = Column(Float, default=None)
    remaining = Column(Float, default=None)
    net_gain = Column(Float, default=0)
    cost = Column(Float, default=0)
    last_reported_price = Column(Float, default=None)
    last_reported_price_datetime = Column(DateTime, default=None)
    high_water_mark = Column(Float, default=None)
    high_water_mark_datetime = Column(DateTime, default=None)
    updated_at = Column(DateTime, default=None)
    status = Column(String, default=TradeStatus.CREATED.value)
    # Stop losses should be actively loaded
    stop_losses = relationship(
        'SQLTradeStopLoss',
        back_populates='trade',
        lazy='joined'
    )
    # Take profits should be actively loaded
    take_profits = relationship(
        'SQLTradeTakeProfit',
        back_populates='trade',
        lazy='joined'
    )

    def __init__(
        self,
        buy_order,
        target_symbol,
        trading_symbol,
        opened_at,
        amount,
        available_amount,
        filled_amount,
        remaining,
        status=TradeStatus.CREATED.value,
        closed_at=None,
        updated_at=None,
        net_gain=0,
        cost=0,
        last_reported_price=None,
        last_reported_price_datetime=None,
        high_water_mark=None,
        high_water_mark_datetime=None,
        sell_orders=[],
        stop_losses=[],
        take_profits=[],
    ):
        self.orders = [buy_order]
        self.open_price = buy_order.price
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.closed_at = closed_at
        self.amount = amount
        self.available_amount = available_amount
        self.filled_amount = filled_amount
        self.remaining = remaining
        self.net_gain = net_gain
        self.cost = cost
        self.last_reported_price = last_reported_price
        self.last_reported_price_datetime = last_reported_price_datetime
        self.high_water_mark = high_water_mark
        self.high_water_mark_datetime = high_water_mark_datetime
        self.opened_at = opened_at
        self.updated_at = updated_at
        self.status = status
        self.stop_losses = stop_losses
        self.take_profits = take_profits

        if sell_orders is not None:
            self.orders.extend(sell_orders)
