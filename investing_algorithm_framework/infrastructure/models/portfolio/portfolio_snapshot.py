from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PortfolioSnapshot
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPortfolioSnapshot(
    PortfolioSnapshot, SQLBaseModel, SQLAlchemyModelExtension
):
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(String, nullable=False)
    trading_symbol = Column(String, nullable=False)
    pending_value = Column(String, nullable=False, default=0)
    unallocated = Column(String, nullable=False, default=0)
    total_net_gain = Column(String, nullable=False, default=0)
    total_revenue = Column(String, nullable=False, default=0)
    total_cost = Column(String, nullable=False, default=0)
    cash_flow = Column(String, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=0)
    position_snapshots = relationship(
        "SQLPositionSnapshot",
        back_populates="portfolio_snapshot",
        lazy="dynamic",
        cascade="all,delete",
    )


