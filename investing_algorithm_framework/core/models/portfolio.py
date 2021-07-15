from datetime import datetime

from sqlalchemy import UniqueConstraint

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderSide
from investing_algorithm_framework.core.models.model_extension \
    import ModelExtension


class Portfolio(db.Model, ModelExtension):
    """
    Class Portfolio: a database model for an
    AlgorithmPortfolio instance.

    Attributes:
    A AlgorithmPortfolio instance consists out of the following attributes:

    - id: unique identification
    - algorithm_id: reference to the Algorithm instance (Algorithm Service)
    - free_fraction: fraction of the AlgorithmPortfolio that can be
    freely invested
    - invested_fraction: fraction of the AlgorithmPortfolio that is
    already invested
    - net_profit_percentage: lifetime return of the AlgorithmPortfolio
    - created_at: The datetime the portfolio was created
    - updated_at: The datetime the portfolio was updated

    Relationships:
    - algorithm_orders: all the AlgorithmOrders which belong to the
    AlgorithmPortfolio
    - algorithm_positions: all the AlgorithmPositions which belong to the
    AlgorithmPortfolio

    During creation of a AlgorithmPortfolio, you need to provide an
    Algorithm Id.
    """

    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
    base_currency = db.Column(db.String, nullable=False)
    unallocated = db.Column(db.String, nullable=False, default=0)
    broker = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow())
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow(),
        onupdate=datetime.utcnow()
    )

    # Relationships
    positions = db.relationship(
        "Position",
        back_populates="portfolio",
        cascade="all,delete",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'base_currency', 'broker', name='_base_currency_broker_uc'
        ),
    )

    def __init__(self, base_currency, unallocated, broker, **kwargs):
        self.broker = broker
        self.base_currency = base_currency
        self.unallocated = unallocated
        super(Portfolio, self).__init__(**kwargs)

    def add_buy_order(self, order):
        self._validate_order(order)
        self.validate_buy_order(order)
        self._add_order_to_position(order)

    def validate_buy_order(self, order):

        if not order.trading_symbol == self.base_currency:
            raise OperationalException(
                f"Can't add buy order with trading "
                f"symbol {order.trading_symbol} to "
                f"portfolio with base currency {self.base_currency}"
            )

        # Total price can't be greater then unallocated size
        total_price = order.amount * order.price

        if float(self.unallocated) < total_price:
            raise OperationalException(
                f"Order total: {total_price} {self.base_currency}, is larger "
                f"then unallocated size: {self.unallocated} "
                f"{self.base_currency} of the portfolio"
            )

    def add_sell_order(self, order):
        self._validate_order(order)
        self.validate_sell_order(order)
        self._add_order_to_position(order)

    def validate_sell_order(self, order):
        from .position import Position

        position = Position.query\
            .filter_by(portfolio=self)\
            .filter_by(symbol=order.trading_symbol)\
            .first()

        if position is None:
            raise OperationalException(
                "Can't add sell order to non existing position"
            )

        if position.amount < order.amount:
            raise OperationalException(
                "Order amount is larger then amount of open position"
            )

        if not order.target_symbol == self.base_currency:
            raise OperationalException(
                f"Can't add sell order with target "
                f"symbol {order.target_symbol} to "
                f"portfolio with base currency {self.broker.base_currency}"
            )

    def _validate_order(self, order):
        pass

    def _add_order_to_position(self, order):
        from investing_algorithm_framework.core.models import Position

        if OrderSide.BUY.equals(order.order_side):
            position = Position.query \
                .filter_by(symbol=order.target_symbol) \
                .filter_by(portfolio=self)\
                .first()
        else:
            position = Position.query \
                .filter_by(symbol=order.trading_symbol) \
                .filter_by(portfolio=self) \
                .first()

        if position is None:
            position = Position(symbol=order.target_symbol)
            position.save(db)
            self.positions.append(position)
            db.session.commit()

        position.orders.append(order)

        # Update unallocated
        self._sync_unallocated(order)

        db.session.commit()

    def _sync_unallocated(self, order):
        total = order.amount * order.price
        unallocated = float(self.unallocated)
        if OrderSide.BUY.equals(order.order_side):
            self.unallocated = (unallocated - total).__str__()
        else:
            self.unallocated = (unallocated + total).__str__()

    def __repr__(self):
        return self.repr(
            id=self.id,
            base_currency=self.base_currency,
            unallocated=f"{self.unallocated} {self.base_currency}",
            broker=self.broker,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
