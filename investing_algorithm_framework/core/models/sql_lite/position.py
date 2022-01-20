from abc import abstractmethod
from random import randint

from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.core.models import db, OrderSide, \
    OrderStatus, Position
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
    id = db.Column(
        db.Integer, primary_key=True, unique=True, default=random_id
    )

    # Asset Symbol (e.g. BTC)
    symbol = db.Column(db.String)

    # The price of the asset
    orders = db.relationship(
        "SQLLiteOrder",
        back_populates="position",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    amount = db.Column(db.Float)

    # Relationships
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'))
    portfolio = relationship("SQLLitePortfolio", back_populates="positions")

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'symbol', 'portfolio_id', name='_symbol_portfolio_uc'
        ),
    )

    def __init__(self, symbol):
        self.symbol = symbol
        self.amount = 0

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    @hybrid_property
    def delta(self):
        orders = self.orders\
            .filter_by(order_side=OrderSide.BUY.value) \
            .filter_by(status=OrderStatus.SUCCESS.value) \
            .all()

        delta = 0

        for order in orders:
            delta += order.delta
        return delta

    def get_symbol(self):
        return self.symbol

    def get_orders(self):
        return self.orders.all()

    @abstractmethod
    def get_amount(self):
        return self.amount

    def __repr__(self):
        return self.repr(
            id=self.id,
            symbol=self.symbol,
            amount=self.amount,
        )
