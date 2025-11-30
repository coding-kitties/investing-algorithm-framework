from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, \
    DateTime
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import TradeTakeProfit
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLTradeTakeProfit(
    TradeTakeProfit, SQLBaseModel, SQLAlchemyModelExtension
):
    """
    SQLTradeTakeProfit model

    A trade take profit is a take profit strategy for a trade.

    Attributes:
    - trade (Trade): the trade that the take profit is for
    - percentage (float): the take profit percentage
    - trailing (bool): indicates whether the take profit is trailing
    - sell_percentage (float) the percentage of the trade to sell
         when the take profit is triggered.
    - target_price (float): the target price at which to take profit.
    - sell_prices (String): a serialized list of prices at which
            take profits were executed.
    - sell_dates (String): a serialized list of dates when
            take profits were executed.
    - sell_amount (float): the total amount sold due to take profits.
    - sold_amount (float): the total amount that has been sold due
        to take profits.
    - active (bool): indicates whether the take profit is currently active.
    """

    __tablename__ = "trade_take_profits"
    id = Column(Integer, primary_key=True, unique=True)
    trade_id = Column(Integer, ForeignKey('trades.id'))
    trade = relationship('SQLTrade', back_populates='take_profits')
    trailing = Column(Boolean)
    percentage = Column(Float)
    sell_percentage = Column(Float)
    open_price = Column(Float)
    high_water_mark = Column(Float)
    high_water_mark_date = Column(String)
    sell_prices = Column(String)
    take_profit_price = Column(Float)
    sell_amount = Column(Float)
    sell_dates = Column(String)
    sold_amount = Column(Float)
    active = Column(Boolean)
    triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=None)
    created_at = Column(DateTime)
    updated_at = Column(DateTime, default=None)
