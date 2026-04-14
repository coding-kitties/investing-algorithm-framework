from sqlalchemy import Column, BigInteger, Sequence, String, ForeignKey, \
    Double
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import PositionSnapshot
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPositionSnapshot(
    SQLBaseModel, PositionSnapshot, SQLAlchemyModelExtension
):
    __tablename__ = "position_snapshots"
    id = Column(BigInteger, Sequence("position_snapshots_id_seq"), primary_key=True, unique=True)
    symbol = Column(String)
    amount = Column(Double)
    cost = Column(Double)
    portfolio_snapshot_id = Column(
        BigInteger, ForeignKey('portfolio_snapshots.id')
    )
    portfolio_snapshot = relationship(
        "SQLPortfolioSnapshot", back_populates="position_snapshots"
    )
