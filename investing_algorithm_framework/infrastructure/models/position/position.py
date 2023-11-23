from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.domain import Position
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPosition(SQLBaseModel, Position, SQLAlchemyModelExtension):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, unique=True)
    symbol = Column(String)
    amount = Column(Float)
    cost = Column(Float)
    orders = relationship(
        "SQLOrder",
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

    def __init__(
        self,
        symbol,
        amount=0,
        cost=0,
        portfolio_id=None,
    ):
        super(SQLPosition, self).__init__()
        self.symbol = symbol
        self.amount = amount
        self.portfolio_id = portfolio_id
        self.cost = cost

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    def update(self, data):

        if 'amount' in data:
            self.amount = data.pop('amount')

        if 'cost' in data:
            self.cost = data.pop('cost')

        super(SQLPosition, self).update(data)

    @property
    def ccxt_symbol(self):
        return f"{self.symbol}/{self.portfolio.trading_symbol}"
