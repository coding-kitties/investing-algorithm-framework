from datetime import datetime
from random import randint

from sqlalchemy import UniqueConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderSide, \
    OrderStatus, OrderType, Portfolio
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.core.models.sql_lite import SQLLiteOrder
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory


def random_id():
    """
    Function to create a random ID. This function checks first if
    the generated ID is not already taken.
    Returns: random integer that can be used as an ID
    """
    minimal = 100
    maximal = 1000000000000000000
    rand = randint(minimal, maximal)

    while SQLLitePortfolio.query.filter_by(id=rand).first() is not None:
        rand = randint(minimal, maximal)

    return rand


class SQLLitePortfolio(db.Model, Portfolio, SQLAlchemyModelExtension):

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
        "SQLLitePosition",
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
        self.id = random_id()
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
        from investing_algorithm_framework.core.models import SQLLitePosition

        position_ids = self.positions.with_entities(SQLLitePosition.id)

        orders = SQLLiteOrder.query \
            .filter_by(order_side=OrderSide.BUY.value) \
            .filter_by(status=OrderStatus.SUCCESS.value)\
            .filter(SQLLiteOrder.position_id.in_(position_ids)) \
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
        from investing_algorithm_framework.core.models import SQLLitePosition

        position = SQLLitePosition.query \
            .filter_by(symbol=order.target_symbol) \
            .filter_by(portfolio=self) \
            .first()

        if OrderSide.BUY.equals(order.order_side):

            if position is None:
                position = SQLLitePosition(symbol=order.target_symbol)
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
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_side=OrderSide.BUY.value,
    ):
        if OrderType.MARKET.equals(order_type):

            if OrderSide.SELL.equals(order_side):
                order = SQLLiteOrder(
                    target_symbol=target_symbol,
                    trading_symbol=self.trading_symbol,
                    amount_target_symbol=amount_target_symbol,
                    order_type=OrderType.MARKET.value,
                    order_side=OrderSide.SELL.value,
                    price=price
                )
            else:
                raise OperationalException("Buy market order is not supported")
        else:
            order = SQLLiteOrder(
                target_symbol=target_symbol,
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
            import SQLLitePortfolioSnapshot

        SQLLitePortfolioSnapshot\
            .from_portfolio(
                self, creation_datetime, withdrawel=withdrawel, deposit=deposit
            ).save(db, commit=commit)

    def get_id(self):
        return self.id

    def get_identifier(self):
        return self.identifier

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_positions(self, symbol: str = None):
        query_set = self.positions

        if symbol is not None:
            query_set = query_set.filter_by(symbol=symbol)

        return query_set.all()

    def get_number_of_positions(self):
        return self.positions.count()

    def get_number_of_orders(self):
        from investing_algorithm_framework import SQLLitePosition

        position_ids = self.positions.with_entities(SQLLitePosition.id)

        return SQLLiteOrder.query \
            .filter(SQLLiteOrder.position_id.in_(position_ids)) \
            .count()

    def get_orders(
        self,
        status: OrderStatus = None,
        side: OrderSide = None,
        target_symbol: str = None,
        trading_symbol: str = None,
        lazy: bool = False
    ):
        from investing_algorithm_framework.core.models import SQLLitePosition

        position_ids = self.positions.with_entities(SQLLitePosition.id)

        query_set = SQLLiteOrder.query \
            .filter(SQLLiteOrder.position_id.in_(position_ids))

        if status:
            status = OrderStatus.from_value(status)
            query_set = query_set.filter_by(status=status.value)

        if target_symbol:
            query_set = query_set.filter_by(target_symbol=target_symbol)

        if trading_symbol:
            query_set = query_set.filter_by(trading_symbol=trading_symbol)

        if side:
            query_set = query_set.filter_by(order_side=side)

        if lazy:
            return query_set

        return query_set.all()

    def get_unallocated(self):
        return self.unallocated

    def get_allocated(self):
        return self.allocated

    def get_realized(self):
        return self.realized

    def get_total_revenue(self):
        return self.total_revenue

    @staticmethod
    def from_dict(data):
        orders = data.get("orders")
        positions = data.get("positions")

    def to_dict(self):
        orders = self.get_orders()
        positions = self.get_positions()

    def __repr__(self):
        return self.to_string()


# first snapshot on creation of a portfolio
@event.listens_for(SQLLitePortfolio, 'before_insert')
def snapshot_after_insert(mapper, connection, portfolio):
    portfolio.snapshot(commit=False)
