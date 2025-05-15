import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain import OrderType, \
    OrderSide, Order, OrderStatus
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension
from investing_algorithm_framework.infrastructure.models.\
    order_trade_association import order_trade_association

logger = logging.getLogger("investing_algorithm_framework")


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
    price = Column(Float)
    amount = Column(Float)
    remaining = Column(Float, default=None)
    filled = Column(Float, default=None)
    cost = Column(Float, default=0)
    status = Column(String, default=OrderStatus.CREATED.value)
    position_id = Column(Integer, ForeignKey('positions.id'))
    position = relationship("SQLPosition", back_populates="orders")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    order_fee = Column(Float, default=None)
    order_fee_currency = Column(String, default=None)
    order_fee_rate = Column(Float, default=None)
    sell_order_metadata_id = Column(Integer, ForeignKey('orders.id'))
    order_metadata = relationship(
        'SQLOrderMetadata', back_populates='order'
    )

    def update(self, data):

        if "status" in data and data["status"] is not None:
            data["status"] = OrderStatus.from_value(data["status"]).value

        super().update(data)

    @staticmethod
    def from_order(order):
        return SQLOrder(
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
        )

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
