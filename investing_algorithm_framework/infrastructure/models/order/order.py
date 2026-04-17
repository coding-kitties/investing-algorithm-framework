import json
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, reconstructor

from investing_algorithm_framework.domain import OrderType, \
    OrderSide, Order, OrderStatus
from investing_algorithm_framework.infrastructure.database import (
    SQLBaseModel, SqliteDecimal
)
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.infrastructure.models.\
    order_trade_association import order_trade_association

logger = logging.getLogger("investing_algorithm_framework")


def utcnow():
    return datetime.now(tz=timezone.utc)


class SQLOrder(Order, SQLBaseModel, SQLAlchemyModelExtension):
    """
    SQLOrder model based on the Order domain model.
    """
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, unique=True)
    external_id = Column(Integer)
    target_symbol = Column(String)
    trading_symbol = Column(String)
    order_side = Column(String, nullable=False, default=OrderSide.BUY.value)
    order_type = Column(String, nullable=False, default=OrderType.LIMIT.value)
    trades = relationship(
        'SQLTrade', secondary=order_trade_association, back_populates='orders'
    )
    price = Column(SqliteDecimal())
    amount = Column(SqliteDecimal())
    remaining = Column(SqliteDecimal(), default=None)
    filled = Column(SqliteDecimal(), default=None)
    cost = Column(SqliteDecimal(), default=0)
    status = Column(String, default=OrderStatus.CREATED.value)
    position_id = Column(Integer, ForeignKey('positions.id'))
    position = relationship("SQLPosition", back_populates="orders")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    order_fee = Column(SqliteDecimal(), default=None)
    order_fee_currency = Column(String, default=None)
    order_fee_rate = Column(SqliteDecimal(), default=None)
    slippage = Column(SqliteDecimal(), default=None)
    sell_order_metadata_id = Column(Integer, ForeignKey('orders.id'))
    metadata_json = Column(Text, default=None)
    trade_allocations = relationship(
        'SQLTradeAllocation', back_populates='order'
    )

    def __init__(self, metadata=None, **kwargs):
        super().__init__(metadata=metadata, **kwargs)
        # Sync metadata dict to JSON column for DB persistence
        if self.metadata:
            self.metadata_json = json.dumps(self.metadata)

    @reconstructor
    def init_on_load(self):
        """Deserialize metadata from JSON when loaded from DB."""
        if self.metadata_json:
            self.metadata = json.loads(self.metadata_json)
        else:
            self.metadata = {}

    def update(self, data):

        if "metadata" in data:
            metadata_val = data.pop("metadata")
            self.metadata = metadata_val if metadata_val else {}
            self.metadata_json = json.dumps(self.metadata) \
                if self.metadata else None

        if "status" in data and data["status"] is not None:
            data["status"] = OrderStatus.from_value(data["status"]).value

        super().update(data)

    @staticmethod
    def from_order(order):
        sql_order = SQLOrder(
            external_id=order.external_id,
            amount=order.get_amount(),
            filled=order.get_filled(),
            remaining=order.get_remaining(),
            price=order.price,
            order_type=order.get_order_type(),
            order_side=order.get(),
            status=order.get_status(),
            target_symbol=order.get_target_symbol(),
            trading_symbol=order.get_trading_symbol(),
            created_at=order.get_created_at(),
            updated_at=order.get_updated_at(),
            metadata=order.metadata,
        )
        return sql_order

    @staticmethod
    def from_ccxt_order(ccxt_order):
        """
        Create an Order object from a CCXT order object

        Args:
            ccxt_order: CCXT order object

        Returns:
            Order: Order object
        """
        status = OrderStatus.from_value(ccxt_order["status"])
        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]
        ccxt_fee = ccxt_order.get("fee", None)
        order_fee = None
        order_fee_rate = None
        order_fee_currency = None

        if ccxt_fee is not None:
            order_fee = ccxt_fee.get("cost", None)
            order_fee_rate = ccxt_fee.get("rate", None)
            order_fee_currency = ccxt_fee.get("currency", None)

        return Order(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount=ccxt_order.get("amount", None),
            status=status,
            order_type=ccxt_order.get("type", None),
            order_side=ccxt_order.get("side", None),
            filled=ccxt_order.get("filled", None),
            remaining=ccxt_order.get("remaining", None),
            cost=ccxt_order.get("cost", None),
            order_fee=order_fee,
            order_fee_rate=order_fee_rate,
            order_fee_currency=order_fee_currency,
            created_at=ccxt_order.get("datetime", None),
        )

    def __lt__(self, other):
        # Define the less-than comparison based on created_at attribute
        return self.created_at < other.created_at
