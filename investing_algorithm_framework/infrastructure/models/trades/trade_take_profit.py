from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
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
    * trade: Trade - the trade that the take profit is for
    * take_profit: float - the take profit percentage
    * trade_risk_type: TradeRiskType - the type of trade risk, either
        trailing or fixed
    * sell_percentage: float - the percentage of the trade to sell when the
    """

    __tablename__ = "trade_take_profits"
    id = Column(Integer, primary_key=True, unique=True)
    trade_id = Column(Integer, ForeignKey('trades.id'))
    trade = relationship('SQLTrade', back_populates='take_profits')
    trade_risk_type = Column(String)
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
