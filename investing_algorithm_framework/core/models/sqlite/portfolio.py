from datetime import datetime
from random import randint

from sqlalchemy import UniqueConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderSide, \
    OrderStatus, OrderType, Portfolio, Position
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.core.models.sqlite import SQLLiteOrder
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
        db.DateTime, default=datetime.utcnow(), onupdate=datetime.utcnow()
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
        self,
        identifier,
        trading_symbol,
        positions,
        market=None,
        orders=None,
        **kwargs
    ):
        super(SQLLitePortfolio, self).__init__(
            identifier=identifier,
            trading_symbol=trading_symbol,
            market=market,
        )

        self.id = random_id()
        self.realized = 0
        self.total_revenue = 0
        self.total_cost = 0
        self.created_at = datetime.utcnow()

        from investing_algorithm_framework.core.models.sqlite \
            import SQLLitePosition

        if positions is not None:
            for position in positions:
                self.positions.append(SQLLitePosition.from_position(position))

    def add_order(self, order):
        self._validate_order(order)
        self._add_order_to_position(order)
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

        if OrderSide.BUY.equals(order.side):

            if position is None:
                position = SQLLitePosition(
                    symbol=order.target_symbol, amount=0
                )
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
        algorithm_context,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        type=OrderType.LIMIT,
        status=OrderStatus.TO_BE_SENT,
        side=OrderSide.BUY.value
    ):
        return SQLLiteOrder(
            reference_id=None,
            type=type,
            status=status,
            side=side,
            initial_price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol(),
            price=price
        )

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
        return self._positions.count()

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

    def get_unallocated(self) -> Position:
        return self.positions.filter_by(symbol=self.trading_symbol).first()

    def get_allocated(self):
        allocated = 0

        for position in self.positions.all():
            allocated += position.get_allocated()
        return allocated

    def set_positions(self, positions):
        pass

    def set_orders(self, orders):
        pass

    def get_realized(self):
        return self.realized

    def get_total_revenue(self):
        return self.total_revenue

    def __repr__(self):
        return self.to_string()
