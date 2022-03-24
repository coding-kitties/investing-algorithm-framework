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

    id = db.Column(db.Integer, primary_key=True, unique=True)
    target_symbol = db.Column(db.String)
    trading_symbol = db.Column(db.String)
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
            'target_symbol', 'portfolio_id', name='_symbol_portfolio_uc'
        ),
    )

    def __init__(
        self,
        target_symbol,
        trading_symbol=None,
        amount=0,
        price=None,
        orders=None
    ):
        super(SQLLitePosition, self).__init__(
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            amount=amount,
            price=price,
            orders=orders
        )
        self.id = random_id()

    @validates('id', 'target_symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    def get_symbol(self):
        return f"{self.get_target_symbol().upper()}" \
               f"/{self.get_trading_symbol()}"

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
            elif isinstance(order, Order):
                order = SQLLiteOrder.from_order(order)
            elif not isinstance(order, SQLLiteOrder):
                raise OperationalException(
                    "Can't add order that is not an instance "
                    "of an Order object"
                )

            # Check if the reference id is set
            if order.get_reference_id() is None:
                raise OperationalException(
                    "Can't add order to position with no reference id defined"
                )

            # Check if the order belongs to this position
            if order.get_target_symbol() != self.get_target_symbol():
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

            self.update_amount()
            db.session.commit()

    def add_orders(self, orders):
        from investing_algorithm_framework.core.models.sqlite.order \
            import SQLLiteOrder

        if orders is not None:
            for order in orders:

                if isinstance(order, dict):
                    order = Order.from_dict(order)
                elif isinstance(order, Order):
                    order = SQLLiteOrder.from_order(order)
                elif not isinstance(order, SQLLiteOrder):
                    raise OperationalException(
                        "Can't add order that is not an instance "
                        "of an Order object"
                    )

                # Check if the reference id is set
                if order.get_reference_id() is None:
                    raise OperationalException(
                        "Can't add order to position with no reference "
                        "id defined"
                    )

                # Check if the order belongs to this position
                if order.get_target_symbol() != self.get_target_symbol():
                    raise OperationalException(
                        "Order does not belong to this position"
                    )

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

            self.update_amount()
            db.session.commit()

    def update_amount(self):
        from investing_algorithm_framework.core.models import SQLLiteOrder

        buy_orders = SQLLiteOrder.query \
            .filter_by(position=self) \
            .filter_by(status=OrderStatus.CLOSED.value) \
            .filter_by(side=OrderSide.BUY.value).all()

        sell_orders = SQLLiteOrder.query \
            .filter_by(position=self) \
            .filter_by(status=OrderStatus.CLOSED.value) \
            .filter_by(side=OrderSide.SELL.value).all()

        amount = 0

        for order in buy_orders:
            amount += order.get_amount_target_symbol()

        for order in sell_orders:
            amount -= order.get_amount_target_symbol()

        self.amount = amount

    @staticmethod
    def from_position(position):
        sql_lite_position = SQLLitePosition(
            target_symbol=position.get_target_symbol(),
            trading_symbol=position.get_trading_symbol(),
            amount=position.get_amount(),
            price=position.get_price()
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
            target_symbol=data.get("target_symbol"),
            trading_symbol=data.get("trading_symbol"),
            price=data.get("price", None),
            amount=data.get("amount", None),
            orders=data.get("orders", None)
        )

    def __repr__(self):
        return self.to_string()
