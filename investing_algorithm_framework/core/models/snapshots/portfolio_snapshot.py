from sqlalchemy import UniqueConstraint
from datetime import datetime
from investing_algorithm_framework.core.models.model_extension import \
    ModelExtension
from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.core.models.snapshots import \
    PositionSnapshot


class PortfolioSnapshot(db.Model, ModelExtension):
    __tablename__ = "portfolio_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, nullable=False)
    broker = db.Column(db.String, nullable=False)
    trading_symbol = db.Column(db.String, nullable=True)
    realized = db.Column(db.Float, nullable=True)
    unallocated = db.Column(db.Float, nullable=True)
    total_revenue = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    # Relationships
    positions = db.relationship(
        "PositionSnapshot",
        back_populates="portfolio",
        lazy="dynamic",
        cascade="all,delete",
    )

    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "created_at",
            name="_portfolio_snapshot_id_created_at_uc"
        ),
    )

    @staticmethod
    def from_portfolio(portfolio, creation_datetime=None):
        snapshot = PortfolioSnapshot()

        from investing_algorithm_framework.core.models import Position

        positions = Position.query.filter_by(id=portfolio.id).all()

        position_snapshots = [
            PositionSnapshot.from_position(position)
            for position in positions
        ]

        snapshot.total_revenue = portfolio.total_revenue
        snapshot.total_cost = portfolio.total_cost
        snapshot.positions = position_snapshots
        snapshot.portfolio_id = portfolio.id
        snapshot.trading_symbol = portfolio.trading_symbol
        snapshot.realized = float(portfolio.realized)
        snapshot.unallocated = float(portfolio.unallocated)
        snapshot.created_at = creation_datetime
        snapshot.portfolio_id = portfolio.id
        snapshot.broker = portfolio.market

        if snapshot.created_at is None:
            snapshot.created_at = datetime.utcnow()

        return snapshot

    def __repr__(self):
        return self.repr(
            created_at=self.created_at,
            portfolio_id=self.portfolio_id,
            trading_symbol=self.trading_symbol,
            total_cost=f"{self.total_cost}",
            unallocated=f"{self.unallocated} {self.trading_symbol}",
            realized=f"{self.realized}",
            total_revenue=f"{self.total_revenue}",
        )
