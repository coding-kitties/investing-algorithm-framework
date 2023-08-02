from sqlalchemy import Column, Integer, String, Float
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates

from investing_algorithm_framework.domain import Portfolio
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPortfolio(SQLBaseModel, Portfolio, SQLAlchemyModelExtension):
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True)
    identifier = Column(String, nullable=False, unique=True)
    trading_symbol = Column(String, nullable=False)
    realized = Column(Float, nullable=False, default=0)
    total_revenue = Column(Float, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0)
    total_net_gain = Column(Float, nullable=False, default=0)
    net_size = Column(Float, nullable=False, default=0)
    unallocated = Column(Float, nullable=False, default=0)
    market = Column(String, nullable=False)
    positions = relationship(
        "SQLPosition",
        back_populates="portfolio",
        lazy="dynamic",
        cascade="all,delete",
    )
    __table_args__ = (
        UniqueConstraint(
            'trading_symbol',
            'identifier',
            name='_trading_currency_identifier_uc'
        ),
    )

    @validates('trading_symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)

        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    def __init__(self, trading_symbol, market, unallocated, identifier=None):

        if identifier is None:
            identifier = market

        super().__init__(
            trading_symbol=trading_symbol,
            market=market,
            identifier=identifier,
            net_size=unallocated,
            unallocated=unallocated,
            realized=0,
            total_revenue=0,
            total_cost=0,
        )
