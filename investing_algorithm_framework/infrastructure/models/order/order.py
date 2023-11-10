import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain.models import OrderType, \
    OrderSide, Order, OrderStatus, OrderFee
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension

logger = logging.getLogger("investing_algorithm_framework")


class SQLOrder(Order, SQLBaseModel, SQLAlchemyModelExtension):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, unique=True)
    external_id = Column(Integer)
    target_symbol = Column(String)
    trading_symbol = Column(String)
    side = Column(String, nullable=False, default=OrderSide.BUY.value)
    order_type = Column(String, nullable=False, default=OrderType.LIMIT.value)
    price = Column(String)
    amount = Column(String)
    filled_amount = Column(String)
    remaining_amount = Column(String)
    cost = Column(String)
    status = Column(String)
    position_id = Column(Integer, ForeignKey('positions.id'))
    position = relationship("SQLPosition", back_populates="orders")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    trade_closed_at = Column(DateTime, default=None)
    trade_closed_price = Column(String, default=None)
    trade_closed_amount = Column(String, default=None)
    net_gain = Column(String, default=0)
    fee = relationship(
        "SQLOrderFee",
        uselist=False,
        back_populates="order",
        cascade="all, delete"
    )

    @staticmethod
    def from_order(order):
        return SQLOrder(
            external_id=order.external_id,
            amount=order.get_amount(),
            price=order.price,
            order_type=order.get_order_type(),
            side=order.get_side(),
            status=order.get_status(),
            target_symbol=order.get_target_symbol(),
            trading_symbol=order.get_trading_symbol(),
            created_at=order.get_created_at(),
            updated_at=order.get_updated_at(),
            trade_closed_at=order.get_trade_closed_at(),
            trade_closed_price=order.get_trade_closed_price(),
            trade_closed_amount=order.get_trade_closed_amount(),
            net_gain=order.get_net_gain(),
        )

    @staticmethod
    def from_ccxt_order(ccxt_order):
        status = OrderStatus.from_value(ccxt_order["status"])
        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]
        return Order(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount=ccxt_order.get("amount", None),
            status=status,
            order_type=ccxt_order.get("type", None),
            side=ccxt_order.get("side", None),
            filled_amount=ccxt_order.get("filled", None),
            remaining_amount=ccxt_order.get("remaining", None),
            cost=ccxt_order.get("cost", None),
            fee=OrderFee.from_ccxt_fee(ccxt_order.get("fee", None)),
            created_at=ccxt_order.get("datetime", None),
        )

    def __lt__(self, other):
        # Define the less-than comparison based on created_at attribute
        return self.created_at < other.created_at
