from datetime import datetime
from random import randint

from sqlalchemy import UniqueConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

from investing_algorithm_framework.core.models import db, OrderSide, Order, \
    OrderStatus, OrderType
from investing_algorithm_framework.core.exceptions import OperationalException
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
    market = db.Column(db.String, nullable=False)
    identifier = db.Column(db.String, nullable=False)
    trading_symbol = db.Column(db.String, nullable=False)
    unallocated = db.Column(db.Float, nullable=False, default=0)
    realized = db.Column(db.Float, nullable=False, default=0)

    total_revenue = db.Column(db.Float, nullable=False, default=0)
    total_cost = db.Column(db.Float, nullable=False, default=0)

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
        lazy="dynamic",
        cascade="all,delete",
    )

    # Constraints
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
            self, trading_symbol, unallocated, identifier, market, **kwargs
    ):
        self.id = randint(1, 10)
        self.identifier = identifier
        self.trading_symbol = trading_symbol
        self.unallocated = unallocated
        self.realized = 0
        self.total_revenue = 0
        self.total_cost = 0
        self.market = market
        self.created_at = datetime.utcnow()
        super(Portfolio, self).__init__(**kwargs)

    @hybrid_property
    def allocated(self):
        from investing_algorithm_framework.core.models import Position

        position_ids = self.positions.with_entities(Position.id)

        orders = Order.query \
            .filter_by(order_side=OrderSide.BUY.value) \
            .filter_by(status=OrderStatus.SUCCESS.value)\
            .filter(Order.position_id.in_(position_ids)) \
            .all()

        allocated = 0

        for order in orders:
            allocated += order.current_value

        return allocated

    @hybrid_property
    def allocated_percentage(self):

        # Prevent zero division
        if self.allocated == 0 and self.unallocated == 0:
            return 0

        return (self.allocated / (self.allocated + self.unallocated)) * 100

    @hybrid_property
    def unallocated_percentage(self):

        # Prevent zero division
        if self.allocated == 0 and self.unallocated == 0:
            return 0

        return (self.unallocated / self.unallocated + self.allocated) * 100

    def add_order(self, order):
        self._validate_order(order)
        self._add_order_to_position(order)

        order.update(db, {"status": OrderStatus.TO_BE_SENT.value}, commit=True)

        if OrderSide.BUY.equals(order.order_side):
            self.unallocated -= order.amount_trading_symbol

            # Create the snapshot at the time the order was created
            self.snapshot(creation_datetime=order.created_at)

        db.session.commit()

    def _validate_order(self, order):
        order_validator = OrderValidatorFactory.of(self.market)
        order_validator.validate(order, self)

    def _add_order_to_position(self, order):
        from investing_algorithm_framework.core.models import Position

        position = Position.query \
            .filter_by(symbol=order.target_symbol) \
            .filter_by(portfolio=self) \
            .first()

        if OrderSide.BUY.equals(order.order_side):

            if position is None:
                position = Position(symbol=order.target_symbol)
                position.save(db)
                self.positions.append(position)
                db.session.commit()
        else:

            if position is None:
                raise OperationalException(
                    "Sell order can 't be added to non existing position"
                )

        position.orders.append(order)
        db.session.commit()

    def create_order(
        self,
        context,
        order_type,
        symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_side=OrderSide.BUY.value,
        validate_pair=True,
    ):

        market_service = context.get_market_service(self.market)

        if validate_pair:

            # Check if pair exists
            if not market_service.pair_exists(
                symbol, self.trading_symbol
            ):
                raise OperationalException(
                    f"Can't receive price data for "
                    f"pair {symbol} {self.trading_symbol}"
                )

        from investing_algorithm_framework.core.models import Order

        if OrderType.MARKET.equals(order_type):

            if OrderSide.SELL.equals(order_side):
                order = Order(
                    target_symbol=symbol,
                    trading_symbol=self.trading_symbol,
                    amount_target_symbol=amount_target_symbol,
                    order_type=OrderType.MARKET.value,
                    order_side=OrderSide.SELL.value,
                    price=price
                )
            else:
                raise OperationalException("Buy market order is not supported")
        else:
            order = Order(
                target_symbol=symbol,
                trading_symbol=self.trading_symbol,
                amount_target_symbol=amount_target_symbol,
                amount_trading_symbol=amount_trading_symbol,
                order_type=order_type,
                order_side=order_side,
                price=price
            )

        return order

    def withdraw(self, amount, creation_datetime=datetime.utcnow()):

        if amount > self.unallocated:
            raise OperationalException(
                "Withdrawal is larger then unallocated size"
            )

        self.unallocated -= amount
        db.session.commit()
        self.snapshot(creation_datetime=creation_datetime, withdrawel=amount)

    def deposit(self, amount, creation_datetime=datetime.utcnow()):
        self.unallocated += amount
        db.session.commit()
        self.snapshot(creation_datetime=creation_datetime, deposit=amount)

    def update(self, db, data, commit: bool = False, **kwargs):
        self.updated_at = datetime.utcnow()
        unallocated = data.pop("unallocated", None)

        if unallocated is not None:
            self.unallocated += unallocated
            self.snapshot()

        super(Portfolio, self).update(db, data, **kwargs)

    def snapshot(
        self, withdrawel=0, deposit=0, commit=True, creation_datetime=None
    ):
        from investing_algorithm_framework.core.models.snapshots \
            import PortfolioSnapshot

        PortfolioSnapshot\
            .from_portfolio(
                self, creation_datetime, withdrawel=withdrawel, deposit=deposit
            ).save(db, commit=commit)

    def __repr__(self):
        return self.repr(
            id=self.id,
            trading_symbol=self.trading_symbol,
            unallocated=f"{self.unallocated} {self.trading_symbol}",
            realized=f"{self.realized}",
            total_revenue=f"{self.total_revenue}",
            identifier=self.identifier,
            created_at=self.created_at,
            updated_at=self.updated_at
        )


# first snapshot on creation of a portfolio
@event.listens_for(Portfolio, 'before_insert')
def snapshot_after_insert(mapper, connection, portfolio):
    portfolio.snapshot(commit=False)
