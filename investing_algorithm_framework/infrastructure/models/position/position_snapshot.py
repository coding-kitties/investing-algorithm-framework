from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PositionSnapshot
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPositionSnapshot(
    SQLBaseModel, PositionSnapshot, SQLAlchemyModelExtension
):
    __tablename__ = "position_snapshots"
    id = Column(Integer, primary_key=True, unique=True)
    symbol = Column(String)
    amount = Column(Float)
    cost = Column(Float)
    portfolio_snapshot_id = Column(Integer, ForeignKey('portfolio_snapshots.id'))
    portfolio_snapshot = relationship(
        "SQLPortfolioSnapshot", back_populates="position_snapshots"
    )
