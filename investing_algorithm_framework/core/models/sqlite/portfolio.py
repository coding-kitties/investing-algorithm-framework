from datetime import datetime
from random import randint
from typing import List

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import validates

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderSide, \
    OrderStatus, OrderType, Portfolio, Position
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.core.models.sqlite import SQLLiteOrder


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
    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
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
        orders=None,
        **kwargs
    ):
        super(SQLLitePortfolio, self).__init__(
            identifier=identifier,
            trading_symbol=trading_symbol,
        )

        self.id = random_id()
        self.realized = 0
        self.total_revenue = 0
        self.total_cost = 0
        self.created_at = datetime.utcnow()

        if positions is not None:
            self.add_positions(positions)

        if orders is not None:
            self.add_orders(orders)

    def add_order(self, order):
        position = self.positions \
            .filter_by(target_symbol=order.get_target_symbol()) \
            .first()

        if position is None:
            from investing_algorithm_framework.core.models.sqlite \
                .position import SQLLitePosition

            position = SQLLitePosition(
                target_symbol=order.get_target_symbol(),
                trading_symbol=self.get_trading_symbol(),
                amount=0
            )
            self.positions.append(position)
            position.add_order(order)
        else:
            position.add_order(order)

        db.session.commit()

    def add_orders(self, orders):

        for order in orders:
            position = self.positions\
                .filter_by(target_symbol=order.get_target_symbol())\
                .first()

            if position is None:
                from investing_algorithm_framework.core.models.sqlite\
                    .position import SQLLitePosition

                position = SQLLitePosition(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=self.get_trading_symbol(),
                    amount=0
                )
                position.add_order(order)
                self.positions.append(position)
            else:
                position.add_order(order)

            db.session.commit()

    def add_position(self, position):
        from investing_algorithm_framework.core.models import SQLLitePosition

        if isinstance(position, dict):
            position = SQLLitePosition.from_dict(position)
        elif isinstance(position, Position):
            position = SQLLitePosition.from_position(position);
        elif not isinstance(position, Position):
            raise OperationalException(
                "Can't add position that is not an instance "
                "of a Position object"
            )

        if not isinstance(position, SQLLitePosition):
            raise OperationalException("The object is not a Position")

        matching_position = SQLLitePosition.query\
            .filter_by(portfolio=self)\
            .filter_by(target_symbol=position.get_target_symbol())\
            .first()

        if matching_position is not None:
            matching_position.set_amount(position.get_amount())
            matching_position.set_price(position.get_price())
            db.session.commit()
        else:
            position.set_trading_symbol(self.get_trading_symbol())
            self.positions.append(position)
            db.session.commit()

    def add_positions(self, positions):
        for position in positions:
            from investing_algorithm_framework.core.models import \
                SQLLitePosition

            if isinstance(position, dict):
                position = SQLLitePosition.from_dict(position)
            elif isinstance(position, Position):
                position = SQLLitePosition.from_position(position);
            elif not isinstance(position, Position):
                raise OperationalException(
                    "Can't add position that is not an instance "
                    "of a Position object"
                )

            if not isinstance(position, SQLLitePosition):
                raise OperationalException("The object is not a Position")

            matching_position = SQLLitePosition.query \
                .filter_by(portfolio=self) \
                .filter_by(target_symbol=position.get_target_symbol()) \
                .first()

            if matching_position is not None:
                matching_position.set_amount(position.get_amount())
                matching_position.set_price(position.get_price())
                db.session.commit()
            else:
                position.set_trading_symbol(self.get_trading_symbol())
                self.positions.append(position)
                db.session.commit()

    def create_order(
        self,
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

    def get_number_of_positions(self):
        return len(self.get_positions())

    def get_number_of_orders(self):
        from investing_algorithm_framework import SQLLitePosition

        position_ids = self.positions.with_entities(SQLLitePosition.id)

        return SQLLiteOrder.query \
            .filter(SQLLiteOrder.position_id.in_(position_ids)) \
            .count()

    def get_order(self, reference_id):
        from investing_algorithm_framework.core.models import SQLLitePosition
        position_ids = SQLLitePosition.query\
            .filter_by(portfolio=self)\
            .with_entities(SQLLitePosition.id)

        return SQLLiteOrder.query\
            .filter(SQLLiteOrder.position_id.in_(position_ids))\
            .filter_by(reference_id=reference_id)\
            .first()

    def get_orders(
        self,
        type=None,
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
            side = OrderSide.from_value(side)
            query_set = query_set.filter_by(side=side.value)

        if type:
            type = OrderType.from_value(type)
            query_set = query_set.filter_by(type=type.value)

        if lazy:
            return query_set

        return query_set.all()

    def get_position(self, target_symbol) -> Position:
        from investing_algorithm_framework.core.models.sqlite \
            import SQLLitePosition

        if target_symbol is not None:
            target_symbol = target_symbol.upper()
            query_set = self.positions
            return query_set.filter()\
                .filter(SQLLitePosition.amount > 0)\
                .filter_by(target_symbol=target_symbol)\
                .first()
        else:
            return None

    def get_positions(self) -> List[Position]:
        return self.positions.all()

    def get_unallocated(self) -> Position:
        return self.positions.filter_by(target_symbol=self.trading_symbol).first()

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

    @staticmethod
    def from_dict(data):
        if data is None:
            return None

        portfolio = SQLLitePortfolio.query\
            .filter_by(identifier=data.get("identifier", None))\
            .first()

        if portfolio is None:
            return SQLLitePortfolio(
                identifier=data.get("identifier", None),
                trading_symbol=data.get("trading_symbol", None),
                positions=data.get("positions", None),
                orders=data.get("orders", None)
            )

        portfolio.add_positions(data.get("orders", None))
        # portfolio.add_orders(data.get("orders", None))
        return portfolio

    def updated(self):
        self.updated_at = datetime.utcnow()
        db.session.commit()
