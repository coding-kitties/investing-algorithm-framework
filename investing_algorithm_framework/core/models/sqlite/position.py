from random import randint

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderStatus, \
    Position, Order, OrderType, OrderSide
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension


def random_id():
    """
    Function to create a random ID. This function checks first if
    the generated ID is not already taken.
    Returns: random integer that can be used as an ID
    """
    minimal = 100
    maximal = 1000000000000000000
    rand = randint(minimal, maximal)

    while SQLLitePosition.query.filter_by(id=rand).first() is not None:
        rand = randint(minimal, maximal)

    return rand


class SQLLitePosition(Position, db.Model, SQLAlchemyModelExtension):
    __tablename__ = "positions"

    # Integer id for the Position as the primary key
    id = db.Column(db.Integer, primary_key=True, unique=True)
    symbol = db.Column(db.String)
    amount = db.Column(db.Float)
    price = db.Column(db.Float)
    orders = db.relationship(
        "SQLLiteOrder",
        back_populates="position",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    # Relationships
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'))
    portfolio = relationship("SQLLitePortfolio", back_populates="positions")

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'symbol', 'portfolio_id', name='_symbol_portfolio_uc'
        ),
    )

    def __init__(self, symbol, amount, price=None, orders=None):
        symbol = symbol.upper()
        super().__init__(symbol, amount, price)
        self.id = random_id()
        self.add_orders(orders)

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    def get_symbol(self):
        return self.symbol

    def get_order(self, reference_id):
        return self.orders \
            .filter_by(reference_id=reference_id) \
            .first()

    def get_orders(self, status=None, type=None, side=None):
        query_set = self.orders

        if status is not None:
            query_set = query_set\
                .filter_by(status=OrderStatus.from_value(status).value)

        if type is not None:
            query_set = query_set\
                .filter_by(type=OrderType.from_value(type).value)

        if side is not None:
            query_set = query_set\
                .filter_by(side=OrderSide.from_value(side).value)

        return query_set.all()

    def add_order(self, order):
        from investing_algorithm_framework.core.models.sqlite.order \
            import SQLLiteOrder

        if order is not None:

            if isinstance(order, dict):
                order = Order.from_dict(order)

            # Check if the reference id is set
            if order.get_reference_id() is None:
                raise OperationalException(
                    "Can't add order to position with no reference id defined"
                )

            # Check if the order belongs to this position
            if order.get_target_symbol() != self.get_symbol():
                raise OperationalException(
                    "Order does not belong to this position"
                )

            old_order = SQLLiteOrder.query \
                .filter_by(position=self) \
                .filter_by(reference_id=order.get_reference_id()) \
                .first()

            if old_order is None:
                sqlite_order = SQLLiteOrder.from_order(order)
                self.orders.append(sqlite_order)
            else:
                old_order.update(
                    status=order.get_status(),
                    price=order.get_price(),
                    initial_price=order.get_initial_price(),
                    closing_price=order.get_closing_price(),
                    amount_trading_symbol=order.get_amount_trading_symbol(),
                    amount_target_symbol=order.get_amount_target_symbol()
                )

            db.session.commit()

    def add_orders(self, orders):
        from investing_algorithm_framework.core.models.sqlite.order \
            import SQLLiteOrder

        if orders is not None:
            for order in orders:

                if isinstance(order, dict):
                    order = Order.from_dict(order)

                old_order = SQLLiteOrder.query \
                    .filter_by(reference_id=order.get_reference_id()) \
                    .first()

                if old_order is None:
                    sqlite_order = SQLLiteOrder.from_order(order)
                    self.orders.append(sqlite_order)
                    sqlite_order.save(db)
                else:
                    old_order.update(
                        status=order.get_status(),
                        price=order.get_price(),
                        initial_price=order.get_initial_price(),
                        closing_price=order.get_closing_price(),
                        amount_trading_symbol=order.get_amount_trading_symbol(),
                        amount_target_symbol=order.get_amount_target_symbol()
                    )

            db.session.commit()

    @staticmethod
    def from_position(position):
        sql_lite_position = SQLLitePosition(
            symbol=position.get_symbol(),
            amount=position.get_amount()
        )

        orders = position.get_orders()

        if orders is not None:

            from investing_algorithm_framework.core.models.sqlite \
                import SQLLiteOrder

            for order in orders:
                sql_lite_position.orders.append(SQLLiteOrder.from_order(order))

        return sql_lite_position

    @staticmethod
    def from_dict(data):
        return SQLLitePosition(
            symbol=data.get("symbol"),
            price=data.get("price", None),
            amount=data.get("amount", None),
            orders=data.get("orders", None)
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            symbol=self.symbol,
            amount=self.amount,
        )
