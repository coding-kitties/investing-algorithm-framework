from datetime import datetime

from sqlalchemy import UniqueConstraint

from investing_algorithm_framework.core.models import db, OrderSide, Order, \
    OrderType
from investing_algorithm_framework.core.models.model_extension \
    import ModelExtension
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory


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
    trading_currency = db.Column(db.String, nullable=False)
    unallocated = db.Column(db.String, nullable=False, default=0)
    identifier = db.Column(db.String, nullable=False)
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
        lazy="dynamic",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'trading_currency',
            'identifier',
            name='_trading_currency_identifier_uc'
        ),
    )

    def __init__(self, trading_currency, unallocated, identifier, **kwargs):
        self.identifier = identifier
        self.trading_currency = trading_currency
        self.unallocated = unallocated
        super(Portfolio, self).__init__(**kwargs)

    def add_order(self, order):
        self._validate_order(order)
        self._add_order_to_position(order)

    def _validate_order(self, order):
        order_validator = OrderValidatorFactory.of(self.identifier)
        order_validator.validate(order, self)

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

    def create_buy_order(
            self,
            symbol,
            amount,
            price=0,
            order_type=OrderType.LIMIT.value
    ):
        return Order(
            trading_symbol=self.trading_currency,
            target_symbol=symbol,
            amount=amount,
            price=price,
            order_side=OrderSide.BUY.value,
            order_type=order_type
        )

    def create_sell_order(
            self,
            symbol,
            amount,
            price=0,
            order_type=OrderType.LIMIT.value
    ):
        return Order(
            trading_symbol=symbol,
            target_symbol=self.trading_currency,
            amount=amount,
            price=price,
            order_side=OrderSide.SELL.value,
            order_type=order_type
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            trading_currency=self.trading_currency,
            unallocated=f"{self.unallocated} {self.trading_currency}",
            identifier=self.identifier,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
