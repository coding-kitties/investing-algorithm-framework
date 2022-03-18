import logging
from datetime import datetime
from random import randint

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
        Class SQLLiteOrder: a sqlite database model for an Order instance.

        Attributes:
        An SQLLiteOrder instance consists out of the following attributes:

        - id: unique identification also used externally
        - target_symbol: the target asset symbol of the order
        - trading_symbol: the asset that is traded for the target symbol
        - order side: the side of the order, e.g. BUY or SELL
        - order type: the order type, e.g LIMIT.

        The following attributes are OPTIONAL:

        - price: the price of the target symbol (in trading symbol currency)
        - initial_price: the initial price when the order was executed
        - closing_price: the closing price when the order was closed
        (BUY order only)

        Relations:

        - position: relation to the AlgorithmPosition instances
        of users subscribed to the algorithm
    """

    __tablename__ = "orders"

    id = db.Column(
        db.Integer, primary_key=True, unique=True, default=random_id
    )
    reference_id = db.Column(db.Integer)
    target_symbol = db.Column(db.String)
    trading_symbol = db.Column(db.String)
    side = db.Column(db.String, nullable=False, default=OrderSide.BUY.value)
    type = db.Column(db.String, nullable=False, default=OrderType.LIMIT.value)
    initial_price = db.Column(db.Float)
    closing_price = db.Column(db.Float)
    price = db.Column(db.Float)
    amount = db.Column(db.Float)
    amount_trading_symbol = db.Column(db.Float)
    amount_target_symbol = db.Column(db.Float)
    status = db.Column(db.String)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'))
    position = db.relationship("SQLLitePosition", back_populates="orders")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(
        self,
        side,
        type,
        status,
        symbol=None,
        target_symbol=None,
        trading_symbol=None,
        reference_id=None,
        initial_price=None,
        closing_price=None,
        price=None,
        amount_target_symbol=None,
        amount_trading_symbol=None,
        **kwargs
    ):
        target_symbol = target_symbol.upper()
        trading_symbol = trading_symbol.upper()
        super().__init__(
            symbol=symbol,
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            type=type,
            side=side,
            status=status,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            price=price,
            initial_price=initial_price,
            closing_price=closing_price,
            reference_id=reference_id
        )

        # Convert enums to string
        self.side = OrderSide.from_value(side).value
        self.type = OrderType.from_value(type).value
        self.status = OrderStatus.from_value(status).value

    def set_status(self, status):
        self.status = OrderStatus.from_value(status).value

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
