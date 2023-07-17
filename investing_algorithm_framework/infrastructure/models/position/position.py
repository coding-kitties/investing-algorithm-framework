from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.domain import Position


class SQLPosition(SQLBaseModel, Position, SQLAlchemyModelExtension):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, unique=True)
    symbol = Column(String)
    amount = Column(Float)
    orders = relationship(
        "SQLOrder",
        back_populates="position",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    position_costs = relationship(
        "SQLPositionCost",
        back_populates="position",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
    portfolio = relationship("SQLPortfolio", back_populates="positions")
    __table_args__ = (
        UniqueConstraint(
            'symbol', 'portfolio_id', name='_symbol_portfolio_uc'
        ),
    )
    _cost = 0

    def __init__(
        self,
        symbol,
        amount=0,
        portfolio_id=None
    ):
        super(SQLPosition, self).__init__()
        self.symbol = symbol
        self.amount = amount
        self.portfolio_id = portfolio_id
        self.cost = 0

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    @property
    def ccxt_symbol(self):
        return f"{self.symbol}/{self.portfolio.trading_symbol}"
