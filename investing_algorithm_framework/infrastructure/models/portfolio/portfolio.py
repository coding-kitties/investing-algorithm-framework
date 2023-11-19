from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates

from datetime import datetime
from investing_algorithm_framework.domain import Portfolio, \
    parse_decimal_to_string
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPortfolio(Portfolio, SQLBaseModel, SQLAlchemyModelExtension):
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True)
    identifier = Column(String, nullable=False, unique=True)
    trading_symbol = Column(String, nullable=False)
    realized = Column(String, nullable=False, default=0)
    total_revenue = Column(String, nullable=False, default=0)
    total_cost = Column(String, nullable=False, default=0)
    total_net_gain = Column(String, nullable=False, default=0)
    total_trade_volume = Column(String, nullable=False, default=0)
    net_size = Column(String, nullable=False, default=0)
    unallocated = Column(String, nullable=False, default=0)
    market = Column(String, nullable=False)
    positions = relationship(
        "SQLPosition",
        back_populates="portfolio",
        lazy="dynamic",
        cascade="all,delete",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
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

    def __init__(
        self,
        trading_symbol,
        market,
        unallocated,
        identifier=None,
        created_at=None,
    ):

        if identifier is None:
            identifier = market

        if created_at is None:
            created_at = datetime.utcnow()

        super().__init__(
            trading_symbol=trading_symbol,
            market=market,
            identifier=identifier,
            net_size=parse_decimal_to_string(unallocated),
            unallocated=parse_decimal_to_string(unallocated),
            realized=0,
            total_revenue=0,
            total_cost=0,
            created_at=created_at,
        )

    def update(self, data):

        if "net_size" in data:
            self.net_size = parse_decimal_to_string(data.pop("net_size"))

        if "unallocated" in data:
            self.unallocated = parse_decimal_to_string(data.pop("unallocated"))

        if "realized" in data:
            self.realized = parse_decimal_to_string(data.pop("realized"))

        if "total_revenue" in data:
            self.total_revenue = parse_decimal_to_string(
                data.pop("total_revenue")
            )

        if "total_trade_volume" in data:
            self.total_trade_volume = parse_decimal_to_string(
                data.pop("total_trade_volume")
            )

        if "total_cost" in data:
            self.total_cost = parse_decimal_to_string(data.pop("total_cost"))

        if "total_net_gain" in data:
            self.total_net_gain = parse_decimal_to_string(
                data.pop("total_net_gain")
            )

        super().update(data)
        return self
