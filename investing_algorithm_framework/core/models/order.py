from datetime import datetime
from random import randint

from sqlalchemy.orm import relationship, validates

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
    __tablename__ = "orders"

    # Integer id for the Order as the primary key
    id = db.Column(
        db.Integer,
        primary_key=True,
        unique=True,
        default=random_id
    )

    # order type (sell/buy)
    order_side = db.Column(db.String)

    # order_type
    order_type = db.Column(db.String, default=OrderType.LIMIT.value)

    # Asset specifications
    target_symbol = db.Column(db.String)
    trading_symbol = db.Column(db.String)

    # Set to true, if order is completed at Binance platform
    executed = db.Column(db.Boolean, default=False)
    successful = db.Column(db.Boolean, default=False, nullable=False)

    # The price of the asset
    price = db.Column(db.Float)
    amount = db.Column(db.Float)

    # Reference to oder on the exchange
    exchange_id = db.Column(db.String)

    # Date Time of creation
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow(),
        onupdate=datetime.utcnow()
    )
    created_at = db.Column(db.DateTime, default=datetime.now())

    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'))
    position = relationship("Position", back_populates="orders")

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
        super(Order, self).__init__(**kwargs)

    @validates(
        'id',
        'target_symbol',
        'trading_symbol',
        'order_side',
        'order_type',
        'price',
        'amount',
    )
    def _write_once(self, key, value):
        existing = getattr(self, key)

        if existing is not None:
            raise ValueError("{} is write-once".format(key))

        return value

    def __repr__(self):
        return self.repr(
            id=self.id,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            amount=self.amount,
            price=self.price,
            total_price=(self.amount * self.price),
            created_at=self.created_at,
            executed=self.executed,
            successful=self.successful,
            position=self.position_id
        )
