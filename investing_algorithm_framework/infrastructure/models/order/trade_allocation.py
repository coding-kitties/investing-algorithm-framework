import logging

from sqlalchemy import Column, BigInteger, Sequence, ForeignKey, Double
from sqlalchemy.orm import relationship

from investing_algorithm_framework.infrastructure.database import SQLBaseModel
from investing_algorithm_framework.infrastructure.models.model_extension \
    import SQLAlchemyModelExtension

logger = logging.getLogger("investing_algorithm_framework")


class SQLTradeAllocation(SQLBaseModel, SQLAlchemyModelExtension):
    """
    Allocation ledger that records how sell order proceeds map back to
    open trades (and optionally to stop-losses / take-profits).

    Trades and sell orders have a many-to-many relationship:
    - One sell order can close multiple trades (e.g. sell 10 units across
      three trades of 4, 4, and 2 via FIFO).
    - One trade can be partially closed by multiple sell orders (e.g.
      sell 3 of a 10-unit trade now, sell the remaining 7 later).

    This table is the junction record that captures each allocation with
    its own amount. Without it, there is no way to:
    - Reverse a cancellation (restore the exact amounts to the exact
      trades that were affected).
    - Track partial fills (`amount_pending` shows how much of the
      allocation is still waiting to be filled by the exchange).
    - Calculate per-trade P&L (need to pair the correct buy price from
      each trade with the sell price and allocated amount).

    Attributes:
        order_id: The sell order this allocation belongs to.
        trade_id: The trade being (partially) closed, or None.
        stop_loss_id: The stop-loss that triggered this sell, or None.
        take_profit_id: The take-profit that triggered this sell, or None.
        amount: The total amount allocated from the sell order to the
            trade / stop-loss / take-profit.
        amount_pending: The portion of `amount` not yet filled by the
            exchange. Decremented as partial fills arrive.
        open_price: The trade's open (buy) price at time of allocation.
        close_price: The sell order price at time of allocation.
        buy_fee: Proportional buy fee for this allocation's amount.
        sell_fee: Proportional sell fee for this allocation's amount.
        net_gain_contribution: The net P&L contribution of this
            allocation: (close_price * amount) - (open_price * amount)
            - buy_fee - sell_fee. Stored at creation time so that
            reversal can simply subtract it without re-derivation.
    """
    __tablename__ = "trade_allocations"
    id = Column(BigInteger, Sequence("trade_allocations_id_seq"), primary_key=True, unique=True)
    order_id = Column(BigInteger, ForeignKey('orders.id'))
    order = relationship('SQLOrder', back_populates='trade_allocations')
    trade_id = Column(BigInteger)
    stop_loss_id = Column(BigInteger)
    take_profit_id = Column(BigInteger)
    amount = Column(Double)
    amount_pending = Column(Double)
    open_price = Column(Double, default=0)
    close_price = Column(Double, default=0)
    buy_fee = Column(Double, default=0)
    sell_fee = Column(Double, default=0)
    net_gain_contribution = Column(Double, default=0)

    def __init__(
        self,
        order_id,
        amount,
        amount_pending,
        trade_id=None,
        stop_loss_id=None,
        take_profit_id=None,
        open_price=0,
        close_price=0,
        buy_fee=0,
        sell_fee=0,
        net_gain_contribution=0,
    ):
        self.order_id = order_id
        self.trade_id = trade_id
        self.stop_loss_id = stop_loss_id
        self.take_profit_id = take_profit_id
        self.amount = amount
        self.amount_pending = amount_pending
        self.open_price = open_price
        self.close_price = close_price
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        self.net_gain_contribution = net_gain_contribution

    def __repr__(self):
        return (
            f"<SQLTradeAllocation(id={self.id}, order_id={self.order_id}, "
            f"trade_id={self.trade_id}, stop_loss_id={self.stop_loss_id}, "
            f"take_profit_id={self.take_profit_id}, amount={self.amount}, "
            f"amount_pending={self.amount_pending}, "
            f"net_gain={self.net_gain_contribution})>"
        )
