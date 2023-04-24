import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from investing_algorithm_framework.domain.models import OrderType, \
    OrderSide, Order, OrderStatus
from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension

logger = logging.getLogger(__name__)


class SQLOrder(SQLBaseModel, Order, SQLAlchemyModelExtension):

    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, unique=True)
    external_id = Column(Integer)
    target_symbol = Column(String)
    trading_symbol = Column(String)
    side = Column(String, nullable=False, default=OrderSide.BUY.value)
    type = Column(String, nullable=False, default=OrderType.LIMIT.value)
    price = Column(Float)
    amount_trading_symbol = Column(Float)
    amount_target_symbol = Column(Float)
    status = Column(String)
    position_id = Column(Integer, ForeignKey('positions.id'))
    position = relationship("SQLPosition", back_populates="orders")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(
        self,
        side,
        type,
        status,
        position_id=None,
        target_symbol=None,
        trading_symbol=None,
        external_id=None,
        price=None,
        amount_target_symbol=None,
        amount_trading_symbol=None,
    ):
        target_symbol = target_symbol.upper()
        trading_symbol = trading_symbol.upper()
        super().__init__(
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            type=type,
            side=side,
            status=status,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            price=price,
            external_id=external_id,
            position_id=position_id
        )
        self.initialize_amount_target_symbol()
        self.initialize_amount_trading_symbol()

    @staticmethod
    def from_order(order):
        return SQLOrder(
            external_id=order.external_id,
            amount_target_symbol=order.get_amount_target_symbol(),
            amount_trading_symbol=order.get_amount_trading_symbol(),
            price=order.price,
            type=order.get_type(),
            side=order.get_side(),
            status=order.get_status(),
            target_symbol=order.get_target_symbol(),
            trading_symbol=order.get_trading_symbol()
        )

    @staticmethod
    def from_ccxt_order(ccxt_order):
        status = OrderStatus.PENDING.value

        if ccxt_order["status"] == "open":
            status = OrderStatus.PENDING.value
        if ccxt_order["status"] == "closed":
            status = OrderStatus.SUCCESS.value
        if ccxt_order["status"] == "canceled":
            status = OrderStatus.CANCELED.value
        if ccxt_order["status"] == "expired":
            status = OrderStatus.FAILED.value
        if ccxt_order["status"] == "rejected":
            status = OrderStatus.FAILED.value

        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]
        return SQLOrder(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount_target_symbol=ccxt_order.get("amount", None),
            status=status,
            type=ccxt_order.get("type", None),
            side=ccxt_order.get("side", None)
        )
