from sqlalchemy import UniqueConstraint, or_
from datetime import datetime
from investing_algorithm_framework.core.models.model_extension import \
    ModelExtension
from investing_algorithm_framework.core.models import db, Order, OrderStatus, \
    OrderSide
from investing_algorithm_framework.core.models.snapshots import \
    PositionSnapshot


class PortfolioSnapshot(db.Model, ModelExtension):
    __tablename__ = "portfolio_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, nullable=False)
    broker = db.Column(db.String, nullable=False)
    trading_symbol = db.Column(db.String, nullable=True)
    realized = db.Column(db.Float, default=0)
    allocated = db.Column(db.Float, default=0)
    unallocated = db.Column(db.Float, default=0)
    total_revenue = db.Column(db.Float, default=0)
    total_value = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=0)
    pending_value = db.Column(db.Float, default=0)

    # Cash flow attributes
    withdrawel = db.Column(db.Float, default=0)
    deposit = db.Column(db.Float, default=0)
    _inner_snapshot = db.Column(db.Boolean, default=False)

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
    def from_portfolio(
        portfolio, creation_datetime=None, withdrawel=0, deposit=0
    ):
        snapshot = PortfolioSnapshot()

        from investing_algorithm_framework.core.models import Position

        positions = Position.query.filter_by(portfolio_id=portfolio.id).all()
        position_snapshots = [
            PositionSnapshot.from_position(position)
            for position in positions
        ]

        snapshot.total_revenue = portfolio.total_revenue
        snapshot.total_cost = portfolio.total_cost
        snapshot.positions = position_snapshots
        snapshot.portfolio_id = portfolio.id
        snapshot.trading_symbol = portfolio.trading_symbol
        snapshot.allocated = portfolio.allocated
        snapshot.realized = portfolio.realized
        snapshot.unallocated = portfolio.unallocated
        snapshot.created_at = creation_datetime
        snapshot.portfolio_id = portfolio.id
        snapshot.broker = portfolio.market
        snapshot.withdrawel = withdrawel
        snapshot.deposit = deposit

        if snapshot.created_at is None:
            snapshot.created_at = datetime.utcnow()

        pending_orders = Order.query\
            .filter(
                or_(
                    Order.status == OrderStatus.PENDING.value,
                    Order.status == OrderStatus.TO_BE_SENT.value
                )
            )\
            .filter_by(order_side=OrderSide.BUY.value)\
            .all()

        pending_value = 0

        for order in pending_orders:
            pending_value += order.amount_trading_symbol

        snapshot.pending_value = pending_value

        total_value = 0
        total_value += portfolio.allocated
        total_value += snapshot.pending_value
        total_value += snapshot.unallocated
        snapshot.total_value = total_value
        return snapshot

    @property
    def cash_flow(self):

        if self.deposit != 0:
            return self.deposit

        if self.withdrawel != 0:
            return -self.withdrawel

        return 0

    def get_total_value(self, asset_prices):

        if self.inner_snapshot:
            return self.total_value

        total_value = 0

        for asset_price in asset_prices:
            position = self.positions\
                .filter_by(symbol=asset_price.target_symbol).first()

            if position is not None:
                total_value += position.amount * asset_price.price

        total_value += self.pending_value
        total_value += self.unallocated
        return total_value

    @property
    def inner_snapshot(self):
        return self._inner_snapshot

    @inner_snapshot.setter
    def inner_snapshot(self, flag):
        self._inner_snapshot = flag

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
