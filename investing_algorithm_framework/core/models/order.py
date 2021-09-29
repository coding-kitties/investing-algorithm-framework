from datetime import datetime
from random import randint

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from sqlalchemy.orm.base import NO_VALUE
from sqlalchemy import event

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderType
from investing_algorithm_framework.core.models.model_extension \
    import ModelExtension
from .order_side import OrderSide


def random_id():
    """
    Function to create a random ID. This function checks first if
    the generated ID is not already taken.
    Returns: random integer that can be used as an ID
    """
    minimal = 100
    maximal = 1000000000000000000
    rand = randint(minimal, maximal)

    while Order.query.filter_by(id=rand).first() is not None:
        rand = randint(minimal, maximal)

    return rand


class Order(db.Model, ModelExtension):
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

        - completed: Flag indicating whether a trade has finished
        - successful: Flag indicating whether a trade was completed successfully
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
    order_reference = db.Column(db.Integer)
    target_symbol = db.Column(db.String)
    trading_symbol = db.Column(db.String)

    order_side = db.Column(
        db.String,
        nullable=False,
        default=OrderSide.BUY.value
    )
    order_type = db.Column(
        db.String,
        nullable=False,
        default=OrderType.LIMIT.value
    )

    # The price and amount of the asset
    price = db.Column(db.Float)
    closing_price = db.Column(db.Float)
    amount = db.Column(db.Float)

    position_id = db.Column(
        db.Integer, db.ForeignKey('positions.id')
    )
    position = db.relationship("Position", back_populates="orders")

    # Standard date time attributes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Post execution
    open = db.Column(db.Boolean)
    successful = db.Column(db.Boolean, default=False)
    executed = db.Column(db.Boolean, default=False)
    executed_at = db.Column(db.DateTime)

    def __init__(
            self,
            order_side,
            order_type,
            target_symbol,
            trading_symbol,
            price,
            amount,
            **kwargs
    ):
        self.order_side = OrderSide.from_string(order_side).value
        self.order_type = OrderType.from_string(order_type).value
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.price = price
        self.amount = amount
        self.open = True

        super(Order, self).__init__(**kwargs)

    @validates(
        'id',
        'target_symbol',
        'trading_symbol',
        'order_side',
        'order_type',
        'price',
    )
    def _write_once(self, key, value):
        existing = getattr(self, key)

        if existing is not None:
            raise ValueError("{} is write-once".format(key))

        return value

    @property
    def current_price(self):
        from investing_algorithm_framework import current_app

        market_service = current_app.algorithm\
            .get_market_service(self.position.portfolio.market)

        current_price = self.price

        try:
            if OrderSide.SELL.equals(self.order_side):
                current_price = market_service.get_price(
                    self.trading_symbol, self.target_symbol
                )
            else:
                current_price = market_service.get_price(
                    self.target_symbol, self.trading_symbol
                )
        except Exception:
            return current_price

        return current_price.price

    @hybrid_property
    def delta(self):

        # Delta is 0 if it is a sell order
        if OrderSide.SELL.equals(self.order_side):
            return 0

        # Current value is 0 when the buy order is not executed
        if not self.executed:
            return 0

        # Orders that are closed have no delta cost
        if not self.open:
            return self.closing_price - self.price

        price = self.current_price

        # With no price data return 0
        if price == -1:
            return 0

        return (price * self.amount) - (self.price * self.amount)

    @hybrid_property
    def percentage(self):

        if OrderSide.SELL.equals(self.order_side):
            return 0

        if not self.executed:
            return 0

        portfolio = self.position.portfolio

        return (
                       self.current_value /
                       (portfolio.allocated + portfolio.unallocated)
               ) * 100

    @hybrid_property
    def percentage_position(self):

        if OrderSide.SELL.equals(self.order_side):
            return 0

        if not self.open:
            return 0

        if not self.executed:
            return 0

        return self.amount / self.position.amount * 100

    @hybrid_property
    def percentage_realized(self):

        if OrderSide.SELL.equals(self.order_side):
            return 0

        if not self.executed:
            return 0

        portfolio = self.position.portfolio

        return (self.amount * self.price) / portfolio.realized * 100

    @hybrid_property
    def current_value(self):

        # Current value is 0 if it is a sell order
        if OrderSide.SELL.equals(self.order_side):
            return 0

        # Current value is 0 when the buy order is not executed
        if not self.executed:
            return 0

        if not self.open:
            return self.closing_price * self.amount

        price = self.current_price
        return price * self.amount

    def set_executed(self):

        if OrderSide.BUY.equals(self.order_side):
            self.executed = True
            self.executed_at = datetime.utcnow()
            self.open = True
            self.position.amount += self.amount
        else:
            self.executed = True
            self.executed_at = datetime.utcnow()
            self.open = False
            self.position.amount -= self.amount

    def update(self, db, data, commit=True, **kwargs):
        self.updated_at = datetime.utcnow()
        super(Order, self).update(db, commit, **kwargs)

    def copy(self, amount=None):

        if amount is None:
            amount = self.amount

        algorithm_order = Order(
            amount=amount,
            price=self.price,
            order_side=self.order_side,
            order_type=self.order_type,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol
        )

        algorithm_order.order_reference = self.order_reference
        algorithm_order.open = self.open
        algorithm_order.executed = self.executed
        algorithm_order.executed_at = self.executed_at
        algorithm_order.updated_at = self.updated_at
        algorithm_order.created_at = self.created_at
        algorithm_order.closing_price = self.closing_price
        algorithm_order.successful = self.successful

        return algorithm_order

    def split(self, amount):

        if not OrderSide.BUY.equals(self.order_side):
            raise OperationalException("Sell order can't be split")

        if not self.executed or not self.open:
            raise OperationalException("Order can't be split")

        if amount <= 0 or amount >= self.amount:
            raise OperationalException("Split amount has a wrong value")

        algorithm_order = self.copy(amount=amount)
        self.amount = self.amount - amount
        self.position.orders.append(algorithm_order)
        db.session.commit()

        return self, algorithm_order

    def __repr__(self):
        return self.repr(
            id=self.id,
            open=self.open,
            order_side=self.order_side,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            amount=self.amount,
            price=self.price,
            created_at=self.created_at,
        )


@event.listens_for(Order.open, "set")
def sync_portfolio_and_position(target, value, old_value, initiator):
    if old_value is NO_VALUE:
        return

    if OrderSide.SELL.equals(target.order_side):

        if old_value and not value:
            sell_amount = target.amount

            # Close open buy orders
            buy_orders = target.position.orders \
                .filter_by(open=True) \
                .filter_by(order_side=OrderSide.BUY.value) \
                .filter_by(executed=True) \
                .order_by(Order.created_at) \
                .all()

            closed_orders = []
            index = 0

            while sell_amount != 0:
                buy_order = buy_orders[index]

                if buy_order.amount <= sell_amount:
                    sell_amount -= buy_order.amount
                    buy_order.closing_price = target.price
                    buy_order.open = False
                    closed_orders.append(buy_order)
                else:
                    remainder = buy_order.amount - sell_amount
                    og, split = buy_order.split(remainder)
                    og.closing_price = target.price
                    og.open = False
                    closed_orders.append(og)
                    sell_amount = 0

                index += 1

            portfolio = target.position.portfolio

            unallocated = 0
            realized = 0

            for closed_order in closed_orders:
                unallocated += closed_order.current_value
                realized += closed_order.delta * closed_order.amount

            portfolio.unallocated += unallocated
            portfolio.realized += realized
            db.session.commit()
