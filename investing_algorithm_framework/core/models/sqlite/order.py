import logging
from datetime import datetime
from random import randint

from sqlalchemy.orm import validates

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderType, \
    OrderStatus, OrderSide, Order
from investing_algorithm_framework.core.models.model_extension \
    import SQLAlchemyModelExtension

logger = logging.getLogger(__name__)


def random_id():
    """
    Function to create a random ID. This function checks first if
    the generated ID is not already taken.
    Returns: random integer that can be used as an ID
    """
    minimal = 100
    maximal = 1000000000000000000
    rand = randint(minimal, maximal)

    while SQLLiteOrder.query.filter_by(id=rand).first() is not None:
        rand = randint(minimal, maximal)

    return rand


class SQLLiteOrder(Order, db.Model, SQLAlchemyModelExtension):
    """
        Class AlgorithmOrder: a database model for an AlgorithmOrder instance.

        Attributes:
        An AlgorithmOrder instance consists out of the following attributes:

        - id: unique identification also used externally
        - target_symbol: the target asset symbol of the order
        - trading_symbol: the asset that is traded for the target symbol
        - order side: the side of the order, e.g. BUY or SELL
        - order type: the order type, e.g LIMIT.

        The following attributes are OPTIONAL:

        - price: the price of the target symbol (in trading symbol currency)
        - amount: the amount of the target symbol

        Updated post-execution:

        for all child orders
        - completed_at: DateTime the order was marked as completed

        Relations:

        - position: relation to the AlgorithmPosition instances
        of users subscribed to the algorithm
    """

    __tablename__ = "orders"

    # Integer id for the Order as the primary key
    id = db.Column(
        db.Integer,
        primary_key=True,
        unique=True,
        default=random_id
    )
    reference_id = db.Column(db.Integer)
    target_symbol = db.Column(db.String)
    trading_symbol = db.Column(db.String)

    side = db.Column(
        db.String,
        nullable=False,
        default=OrderSide.BUY.value
    )
    type = db.Column(
        db.String,
        nullable=False,
        default=OrderType.LIMIT.value
    )

    # The price and amount of the asset
    initial_price = db.Column(db.Float)
    closing_price = db.Column(db.Float)
    price = db.Column(db.Float)
    amount = db.Column(db.Float)
    amount_trading_symbol = db.Column(db.Float)
    amount_target_symbol = db.Column(db.Float)
    status = db.Column(db.String)

    position_id = db.Column(
        db.Integer, db.ForeignKey('positions.id')
    )
    position = db.relationship("SQLLitePosition", back_populates="orders")

    # Standard date time attributes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Post execution
    executed_at = db.Column(db.DateTime)

    def __init__(self, reference_id, side, type, target_symbol, trading_symbol,
                 status, initial_price=None, closing_price=None, price=None,
                 amount_target_symbol=None, amount_trading_symbol=None,
                 **kwargs):

        super().__init__(target_symbol, trading_symbol, type, side, status,
                         amount_trading_symbol, amount_target_symbol, price,
                         initial_price, closing_price, reference_id)

        # Convert enums to string
        self.side = OrderSide.from_value(side).value
        self.type = OrderType.from_value(type).value
        self.status = OrderStatus.from_value(status).value

    def set_amount_target_symbol(self, amount):
        self.amount_target_symbol = amount

        if OrderType.LIMIT.equals(self.order_type):
            self.amount_trading_symbol = \
                self.initial_price * self.amount_target_symbol

    def set_amount_trading_symbol(self, amount):
        self.amount_trading_symbol = amount

        if OrderType.LIMIT.equals(self.order_type):
            self.amount_target_symbol = \
                self.amount_trading_symbol / self.initial_price

    @validates('id', 'target_symbol', 'trading_symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)

        if existing is not None:
            raise ValueError("{} is write-once".format(key))

        return value

    def set_status(self, status):
        self.status = OrderStatus.from_value(status).value

    def update(self, db, data, commit=True, **kwargs):
        self.updated_at = datetime.utcnow()
        super(Order, self).update(db, data, commit, **kwargs)

    def copy(self, amount=None):

        if amount is None:
            amount = self.amount

        if amount > self.amount_target_symbol:
            raise OperationalException("Amount is larger then original order")

        order = SQLLiteOrder(
            reference_id=self.get_reference_id(),
            side=self.get_side(),
            type=self.get_type(),
            status=self.get_status(),
            amount_trading_symbol=self.get_amount_trading_symbol(),
            price=self.initial_price,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            amount_target_symbol=self.amount_target_symbol - (
                    self.amount_target_symbol - amount)
        )

        order.amount_trading_symbol = order.initial_price \
                                      * order.amount_target_symbol
        order.order_reference = self.order_reference
        order.status = self.status
        order.executed_at = self.executed_at
        order.updated_at = self.updated_at
        order.created_at = self.created_at
        order.closing_price = self.closing_price

        self.amount_trading_symbol -= order.amount_trading_symbol
        self.amount_target_symbol -= order.amount_target_symbol

        return order

    def split(self, amount):

        if not OrderSide.BUY.equals(self.order_side):
            raise OperationalException("Sell order can't be split")

        if not OrderStatus.SUCCESS.equals(self.status):
            raise OperationalException("Order can't be split")

        if amount <= 0 or amount >= self.amount_target_symbol:
            raise OperationalException("Split amount has a wrong value")

        algorithm_order = self.copy(amount=amount)
        self.position.orders.append(algorithm_order)
        db.session.commit()

        return self, algorithm_order

    def save(self, db, commit=True):

        if self.position is None:
            raise OperationalException(
                "Can't save order that is not linked to an position"
            )

        super(Order, self).save(db, commit)

    @staticmethod
    def from_order(order):
        return SQLLiteOrder(
            reference_id=order.get_reference_id(),
            amount_target_symbol=order.get_amount_target_symbol(),
            amount_trading_symbol=order.get_amount_trading_symbol(),
            price=order.price,
            initial_price=order.initial_price,
            closing_price=order.closing_price,
            type=order.get_type(),
            side=order.get_side(),
            status=order.get_status(),
            target_symbol=order.get_target_symbol(),
            trading_symbol=order.get_trading_symbol()
        )

    def to_dict(self):
        return {
            "reference_id": self.get_reference_id(),
            "target_symbol": self.get_target_symbol(),
            "trading_symbol": self.get_trading_symbol(),
            "amount_trading_symbol": self.get_amount_trading_symbol(),
            "amount_target_symbol": self.get_amount_target_symbol(),
            "price": self.get_price(),
            "initial_price": self.get_initial_price(),
            "closing_price": self.get_closing_price(),
            "status": self.get_status(),
            "order_type": self.get_type(),
            "order_side": self.get_side()
        }

    def update_with_order(self, order):

        current_status = OrderStatus.from_value(self.status)

        if current_status.equals(order.get_status()):
            self.status = OrderStatus.from_value(order.get_status())

        if self.get_price() != order.get_price():
            self.price = order.get_price()

        if self.get_initial_price() != order.get_initial_price():
            self.initial_price = order.get_initial_price()

        if self.get_closing_price() != order.get_closing_price():
            self.closing_price = order.get_closing_price()

        if self.get_amount_trading_symbol() \
                != order.get_amount_trading_symbol():
            self.amount_trading_symbol = order.get_amount_trading_symbol()

        if self.get_amount_target_symbol() != order.get_amount_target_symbol():
            self.amount_target_symbol = order.get_amount_target_symbol()

        db.session.commit()
