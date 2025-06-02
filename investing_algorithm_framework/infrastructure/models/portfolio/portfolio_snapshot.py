from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PortfolioSnapshot
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPortfolioSnapshot(
    PortfolioSnapshot, SQLBaseModel, SQLAlchemyModelExtension
):
    """
    SQLAlchemy model for portfolio snapshots.

    Portfolio snapshots represent the state of a portfolio at a specific
    point in time.
    """
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(String, nullable=False)
    trading_symbol = Column(String, nullable=False)
    pending_value = Column(Float, nullable=False, default=0)
    unallocated = Column(Float, nullable=False, default=0)
    net_size = Column(Float, nullable=False, default=0)
    total_net_gain = Column(Float, nullable=False, default=0)
    total_revenue = Column(Float, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0)
    cash_flow = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=0)
    position_snapshots = relationship(
        "SQLPositionSnapshot",
        back_populates="portfolio_snapshot",
        lazy="dynamic",
        cascade="all,delete",
    )
