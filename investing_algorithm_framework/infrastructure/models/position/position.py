from decimal import Decimal, localcontext

from sqlalchemy import CheckConstraint, Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, validates

from investing_algorithm_framework.domain import Position
from investing_algorithm_framework.infrastructure.database import (
    SQLBaseModel, SqliteDecimal
)
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension


class SQLPosition(SQLBaseModel, Position, SQLAlchemyModelExtension):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, unique=True)
    symbol = Column(String)
    amount = Column(SqliteDecimal())
    cost = Column(SqliteDecimal())
    long_amount = Column(SqliteDecimal(), nullable=False, default=0)
    short_amount = Column(SqliteDecimal(), nullable=False, default=0)
    long_cost = Column(SqliteDecimal(), nullable=False, default=0)
    short_cost = Column(SqliteDecimal(), nullable=False, default=0)
    orders = relationship(
        "SQLOrder",
        back_populates="position",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
    portfolio = relationship("SQLPortfolio", back_populates="positions")
    __table_args__ = (
        UniqueConstraint(
            'symbol', 'portfolio_id', name='_symbol_portfolio_uc'
        ),
        CheckConstraint('long_amount >= 0'),
        CheckConstraint('short_amount >= 0'),
        CheckConstraint('long_cost >= 0'),
        CheckConstraint('short_cost >= 0'),
    )

    def __init__(
        self,
        symbol,
        amount=0,
        cost=0,
        portfolio_id=None,
        long_amount=None,
        short_amount=None,
        long_cost=None,
        short_cost=None,
    ):
        super(SQLPosition, self).__init__()
        self.symbol = symbol
        self.portfolio_id = portfolio_id
        if all(value is None for value in (
            long_amount, short_amount, long_cost, short_cost
        )):
            self._set_netting_legs(amount, cost)
        else:
            self.long_amount = self._nonnegative(long_amount, 'long_amount')
            self.short_amount = self._nonnegative(
                short_amount, 'short_amount'
            )
            self.long_cost = self._nonnegative(long_cost, 'long_cost')
            self.short_cost = self._nonnegative(short_cost, 'short_cost')
        self._sync_legacy_columns()

    @staticmethod
    def _nonnegative(value, name):
        value = 0 if value is None else value
        if value < 0:
            raise ValueError(f"{name} must be nonnegative")
        return value

    def _set_netting_legs(self, amount, cost):
        amount = 0 if amount is None else amount
        cost = self._nonnegative(cost, 'cost')
        if amount >= 0:
            self.long_amount = amount
            self.short_amount = 0
            self.long_cost = cost
            self.short_cost = 0
        else:
            self.long_amount = 0
            self.short_amount = abs(amount)
            self.long_cost = 0
            self.short_cost = cost

    def _sync_legacy_columns(self):
        self._syncing_legacy = True
        try:
            long_amount = Decimal(str(self.long_amount))
            short_amount = Decimal(str(self.short_amount))
            integer_digits = max(
                long_amount.adjusted(), short_amount.adjusted(), 0
            ) + 1
            fractional_digits = max(
                -long_amount.as_tuple().exponent,
                -short_amount.as_tuple().exponent,
                0,
            )
            with localcontext() as context:
                context.prec = integer_digits + fractional_digits + 1
                self.amount = long_amount - short_amount
            if self.amount > 0:
                self.cost = self.long_cost
            elif self.amount < 0:
                self.cost = self.short_cost
            else:
                self.cost = 0
        finally:
            self._syncing_legacy = False

    @property
    def gross_amount(self):
        return self.long_amount + self.short_amount

    @property
    def net_cost(self):
        return self.long_cost - self.short_cost

    @property
    def gross_cost(self):
        return self.long_cost + self.short_cost

    @validates('id', 'symbol')
    def _write_once(self, key, value):
        existing = getattr(self, key)
        if existing is not None:
            raise ValueError("{} is write-once".format(key))
        return value

    @validates('amount')
    def _sync_amount_to_legs(self, key, value):
        if not getattr(self, '_syncing_legacy', False):
            self._set_netting_legs(value, self.cost or 0)
        return value

    @validates('cost')
    def _sync_cost_to_legs(self, key, value):
        if not getattr(self, '_syncing_legacy', False):
            self._set_netting_legs(self.amount or 0, value)
        return value

    def update(self, data):
        leg_fields = {
            'long_amount', 'short_amount', 'long_cost', 'short_cost'
        }
        if leg_fields.intersection(data):
            for field in leg_fields:
                if field in data:
                    setattr(
                        self, field,
                        self._nonnegative(data.pop(field), field)
                    )
            self._sync_legacy_columns()
            data.pop('amount', None)
            data.pop('cost', None)
            super(SQLPosition, self).update(data)
            return

        if 'amount' in data:
            amount = data.pop('amount')
            cost = data.pop('cost', self.cost or 0)
            self._set_netting_legs(amount, cost)
            self._sync_legacy_columns()

        elif 'cost' in data:
            self._set_netting_legs(self.amount or 0, data.pop('cost'))
            self._sync_legacy_columns()

        super(SQLPosition, self).update(data)

    @property
    def ccxt_symbol(self):
        return f"{self.symbol}/{self.portfolio.trading_symbol}"
