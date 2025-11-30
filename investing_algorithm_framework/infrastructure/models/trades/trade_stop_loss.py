from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, \
    DateTime
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import TradeStopLoss
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLTradeStopLoss(TradeStopLoss, SQLBaseModel, SQLAlchemyModelExtension):
    """
    SQLTradeStopLoss model

    A trade stop loss is a stop loss strategy for a trade.

    Attributes:
     - trade (Trade): the trade that the take profit is for
     - percentage (float): the stop loss percentage
     - trailing (bool): indicates whether the stop loss is trailing
     - sell_percentage (float) the percentage of the trade to sell
        when the stop loss is triggered.
    - open_price (float): the price at which the trade was opened.
    - high_water_mark (float): the highest price reached since the trade
        was opened.
    - high_water_mark_date (String): the date when the high water mark
        was reached.
    - stop_loss_price (float): the calculated stop loss price based on
        the high watermark and percentage.
    - sell_prices (String): a serialized list of prices at which
        stop losses were executed.
    - sell_dates (String): a serialized list of dates when
        stop losses were executed.
    - sell_amount (float): the total amount sold due to stop losses.
    - sold_amount (float): the total amount that has been sold due
        to stop losses.
    - active (bool): indicates whether the stop loss is currently active.
    """

    __tablename__ = "trade_stop_losses"
    id = Column(Integer, primary_key=True, unique=True)
    trade_id = Column(Integer, ForeignKey('trades.id'))
    trade = relationship('SQLTrade', back_populates='stop_losses')
    trailing = Column(Boolean)
    percentage = Column(Float)
    sell_percentage = Column(Float)
    open_price = Column(Float)
    high_water_mark = Column(Float)
    high_water_mark_date = Column(String)
    stop_loss_price = Column(Float)
    sell_prices = Column(String)
    sell_dates = Column(String)
    sell_amount = Column(Float)
    sold_amount = Column(Float)
    active = Column(Boolean)
    triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=None)
    created_at = Column(DateTime)
    updated_at = Column(DateTime, default=None)
