from datetime import datetime
from typing import List

import polars as pl
from polars import DataFrame

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain.constants import DATETIME_FORMAT
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
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
    * amount: float, the amount of the trade
    * open_price: float, the open price of the trade
    * closed_price: float, the closed price of the trade
    * closed_at: datetime, the datetime when the trade was closed
    * opened_at: datetime, the datetime when the trade was opened
    * updated_at: datetime, the datetime when the trade was last updated
    * last_price: float, the current price of the trade
    """

    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, unique=True)
    # A one-to-one relationship for the buy order
    buy_order = relationship(
        'Order',
        primaryjoin="and_(Order.trade_id==Trade.id, Order.side=='buy')",
        uselist=False
    )
    # A one-to-many relationship for the sell orders
    sell_orders = relationship(
        'Order',
        primaryjoin="and_(Order.trade_id==Trade.id, Order.side=='sell')",
        uselist=True
    )
    target_symbol = Column(String)
    trading_symbol = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, default=None)
    closed_price = Column(Float, default=None)
    closed_amount = Column(Float, default=None)
    net_gain = Column(Float, default=0)
    last_reported_price = Column(Float, default=None)

    def __init__(
        self,
        buy_order_id,
        sell_order_ids,
        target_symbol,
        trading_symbol,
        amount,
        open_price,
        opened_at,
        closed_price=None,
        closed_at=None,
        last_reported_price=None,
    ):
        self._buy_order_id = buy_order_id

    @property
    def buy_order_id(self):
        return self._buy_order_id

    @property
    def sell_order_id(self):
        return self._sell_order_id

    @property
    def target_symbol(self):
        return self._target_symbol

    @property
    def trading_symbol(self):
        return self._trading_symbol

    @property
    def symbol(self):
        return f"{self.target_symbol}/{self.trading_symbol}"

    def get_symbol(self):
        return f"{self.target_symbol}/{self.trading_symbol}"

    @property
    def amount(self):
        return self._amount

    def get_amount(self):
        return self.amount

    @property
    def open_price(self):
        return self._open_price

    @property
    def closed_price(self):
        return self._closed_price

    @property
    def closed_at(self):
        return self._closed_at

    @property
    def opened_at(self):
        return self._opened_at

    @property
    def size(self):
        return self.amount * self.open_price

    @property
    def status(self):
        return "CLOSED" if self.closed_at else "OPEN"

    @property
    def net_gain(self):

        if self.closed_at is None:

            if self._current_price is not None:
                return self.amount * (self._current_price - self.open_price)

            return 0

        return self.amount * (self.closed_price - self.open_price)

    @property
    def net_gain_percentage(self):

        if self.closed_at is None:

            if self._current_price is not None:
                return self.net_gain / self.size * 100

            return 0

        return self.net_gain / self.size * 100

    @property
    def duration(self):
        closed_at = self.closed_at

        if closed_at is None:
            closed_at = datetime.utcnow()

        return (closed_at - self.opened_at).total_seconds() / 3600

    @property
    def current_price(self):
        return self._current_price

    @current_price.setter
    def current_price(self, current_price):
        self._current_price = current_price

    @property
    def value(self):

        if self.closed_at is not None:
            return self.amount * self.closed_price

        if self.current_price is None:
            return None

        return self.amount * self.current_price

    @property
    def percentage_change(self):

        if self.closed_at is not None or self.value is None:
            return 0
        value = self.value
        return (value - self.size) / self.size * 100

    def get_percentage_change(self):
        return self.percentage_change

    @property
    def absolute_change(self):

        if self.closed_at is None:
            return 0

        value = self.value
        return value - self.size

    def get_absolute_change(self):
        return self.absolute_change

    def is_manual_stop_loss_trigger(
        self,
        current_price,
        stop_loss_percentage,
        prices: List[float] = None,
        ohlcv_df: DataFrame = None
    ):
        """
        Function to check if the stop loss is triggered for a given trade.

        You can use either the prices list or the ohlcv_df DataFrame to
        calculate the stop loss. The dataframe needs to be a Polars
        DataFrame with the following columns: "Datetime" and "Close".

        You can use the default CCXTOHLCVMarketDataSource to get the ohlcv_df
        DataFrame.

        Stop loss is triggered when the current price is lower than the
        calculated stop loss price. The stop loss price is calculated by
        taking the highest price of the given range. If the highest price
        is lower than the open price, the stop loss price is calculated by
        taking the open price and subtracting the stop loss percentage.
        If the highest price is higher than the open price, the stop loss
        price is calculated by taking the open price and adding the stop
        loss percentage.
        """

        if prices is None and ohlcv_df is None:
            raise OperationalException(
                "Either prices or a polars ohlcv dataframe must be provided"
            )

        if current_price < self.open_price:
            stop_loss_price = self.open_price * \
                              (1 - stop_loss_percentage / 100)
            return current_price <= stop_loss_price
        else:
            # If dataframes are provided, we use the dataframe to calculate
            # the stop loss price
            if ohlcv_df is not None:
                column_type = ohlcv_df['Datetime'].dtype

                if isinstance(column_type, pl.Datetime):
                    filtered_df = ohlcv_df.filter(
                        pl.col('Datetime') >= self.opened_at
                    )
                else:
                    filtered_df = ohlcv_df.filter(
                        pl.col('Datetime') >= self.opened_at.strftime(
                            DATETIME_FORMAT
                        )
                    )

                prices = filtered_df['Close'].to_numpy()

            highest_price = max(prices)
            stop_loss_price = highest_price * (1 - stop_loss_percentage / 100)
            return current_price <= stop_loss_price

    def to_dict(self):
        return {
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "target_symbol": self.target_symbol,
            "trading_symbol": self.trading_symbol,
            "status": self.status,
            "amount": self.amount,
            "open_price": self.open_price,
            "current_price": self.current_price,
            "closed_price": self.closed_price,
            "opened_at": self.opened_at.strftime(DATETIME_FORMAT)
            if self.opened_at else None,
            "closed_at": self.closed_at.strftime(DATETIME_FORMAT)
            if self.closed_at else None,
            "change": self.percentage_change,
            "absolute_change": self.absolute_change,
        }

    @staticmethod
    def from_dict(data):
        return Trade(
            buy_order_id=data["buy_order_id"] if "buy_order_id"
            in data else None,
            sell_order_id=data["sell_order_id"] if "sell_order_id"
            in data else None,
            target_symbol=data["target_symbol"],
            trading_symbol=data["trading_symbol"],
            amount=data["amount"],
            open_price=data["open_price"],
            opened_at=datetime.strptime(
                data["opened_at"], DATETIME_FORMAT
            ),
            closed_price=data["closed_price"],
            closed_at=datetime.strptime(
                data["closed_at"], DATETIME_FORMAT
            ) if data["closed_at"] else None,
            current_price=data["current_price"],
        )

    def __repr__(self):
        return self.repr(
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            status=self.status,
            amount=self.amount,
            open_price=self.open_price,
            current_price=self.current_price,
            closed_price=self.closed_price,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
            value=self.value,
            change=self.percentage_change,
            absolute_change=self.absolute_change,
        )
