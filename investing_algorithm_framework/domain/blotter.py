import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger("investing_algorithm_framework")


class SlippageModel(ABC):
    """
    Abstract base class for slippage models.

    Slippage models determine how the execution price deviates from
    the intended order price. This is used by the SimulationBlotter
    to model realistic order fills during backtesting.
    """

    @abstractmethod
    def calculate_slippage(self, price, order_side, amount=None):
        """
        Calculate the slipped execution price.

        Args:
            price: The intended fill price
            order_side: The side of the order ('BUY' or 'SELL')
            amount: The order amount (for volume-based models)

        Returns:
            float: The adjusted price after slippage
        """
        raise NotImplementedError


class NoSlippage(SlippageModel):
    """No slippage — fills at the exact order price."""

    def calculate_slippage(self, price, order_side, amount=None):
        return price


class PercentageSlippage(SlippageModel):
    """
    Percentage-based slippage model.

    Buy orders fill at a slightly higher price,
    sell orders fill at a slightly lower price.
    """

    def __init__(self, percentage=0.001):
        """
        Args:
            percentage: Slippage as a decimal (0.001 = 0.1%).
        """
        self.percentage = percentage

    def calculate_slippage(self, price, order_side, amount=None):
        from investing_algorithm_framework.domain.models.order.order_side \
            import OrderSide

        if OrderSide.BUY.equals(order_side):
            return price * (1 + self.percentage)
        else:
            return price * (1 - self.percentage)


class FixedSlippage(SlippageModel):
    """
    Fixed amount slippage model.

    Buy orders fill at price + fixed amount,
    sell orders fill at price - fixed amount.
    """

    def __init__(self, amount=0.01):
        """
        Args:
            amount: Fixed slippage amount in price units.
        """
        self.amount = amount

    def calculate_slippage(self, price, order_side, amount=None):
        from investing_algorithm_framework.domain.models.order.order_side \
            import OrderSide

        if OrderSide.BUY.equals(order_side):
            return price + self.amount
        else:
            return price - self.amount


class CommissionModel(ABC):
    """
    Abstract base class for commission models.

    Commission models determine the fee charged for each trade.
    Used by the SimulationBlotter during backtesting.
    """

    @abstractmethod
    def calculate_commission(self, price, amount, order_side):
        """
        Calculate the commission for a trade.

        Args:
            price: The fill price
            amount: The fill amount
            order_side: The side of the order ('BUY' or 'SELL')

        Returns:
            float: The commission amount
        """
        raise NotImplementedError


class NoCommission(CommissionModel):
    """No commission — zero fees."""

    def calculate_commission(self, price, amount, order_side):
        return 0.0


class PercentageCommission(CommissionModel):
    """
    Percentage-based commission model.

    Commission is calculated as a percentage of the total trade value
    (price * amount).
    """

    def __init__(self, percentage=0.001):
        """
        Args:
            percentage: Commission as a decimal (0.001 = 0.1%).
        """
        self.percentage = percentage

    def calculate_commission(self, price, amount, order_side):
        return price * amount * self.percentage


class FixedCommission(CommissionModel):
    """
    Fixed commission per trade, regardless of trade size.
    """

    def __init__(self, amount=1.0):
        """
        Args:
            amount: Fixed commission amount per trade.
        """
        self.amount = amount

    def calculate_commission(self, price, amount, order_side):
        return self.amount


class Transaction:
    """
    Represents a completed fill/transaction recorded by the blotter.

    Transactions provide an audit trail of all order fills, including
    the actual execution price, slippage, and commission.
    """

    def __init__(
        self,
        order_id,
        symbol,
        order_side,
        price,
        amount,
        cost,
        commission=0.0,
        slippage=0.0,
        timestamp=None,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.order_side = order_side
        self.price = price
        self.amount = amount
        self.cost = cost
        self.commission = commission
        self.slippage = slippage
        self.timestamp = timestamp or datetime.now(tz=timezone.utc)

    def to_dict(self):
        timestamp = self.timestamp

        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "order_side": self.order_side,
            "price": self.price,
            "amount": self.amount,
            "cost": self.cost,
            "commission": self.commission,
            "slippage": self.slippage,
            "timestamp": timestamp,
        }

    def __repr__(self):
        return (
            f"Transaction(order_id={self.order_id}, "
            f"symbol={self.symbol}, "
            f"side={self.order_side}, "
            f"price={self.price}, "
            f"amount={self.amount}, "
            f"commission={self.commission})"
        )


class Blotter(ABC):
    """
    Abstract base class for order book management.

    The Blotter centralizes order management logic and sits between
    the strategy (Context) and the order execution layer. It enables:

    - Batch ordering (place multiple orders at once)
    - Transaction tracking (audit trail of all fills)
    - Custom order routing and execution logic
    - Pluggable slippage and commission models

    Usage::

        class SmartOrderRouter(Blotter):
            def place_order(self, order_data, context):
                # Custom routing logic
                return context.create_limit_order(...)

            def cancel_order(self, order_id, context):
                # Custom cancellation logic
                pass

        app.set_blotter(SmartOrderRouter())
    """

    def __init__(self):
        self._config = None
        self._transactions: List[Transaction] = []

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    @abstractmethod
    def place_order(self, order_data, context):
        """
        Place a single order through this blotter.

        Args:
            order_data: Dict with order parameters. Supported keys:
                - target_symbol (str): Required. The symbol to trade.
                - order_side (str/OrderSide): Required. BUY or SELL.
                - price (float): Required for limit orders.
                - order_type (str/OrderType): Default LIMIT.
                - amount (float): Amount to trade.
                - percentage_of_portfolio (float): % of portfolio.
                - percentage_of_position (float): % of position.
                - market (str): The market/exchange.
                - precision (int): Decimal precision for amount.
                - metadata (dict): Additional metadata.
            context: The Context instance.

        Returns:
            Order: The created order.
        """
        raise NotImplementedError

    def batch_order(self, orders_data, context):
        """
        Place multiple orders at once.

        Default implementation places orders sequentially.
        Override for atomic batch behavior or custom routing.

        Args:
            orders_data: List of order data dicts (same format
                as place_order).
            context: The Context instance.

        Returns:
            List[Order]: The created orders.
        """
        results = []

        for data in orders_data:
            order = self.place_order(data, context)
            results.append(order)

        return results

    @abstractmethod
    def cancel_order(self, order_id, context):
        """
        Cancel a specific order.

        Args:
            order_id: The ID of the order to cancel.
            context: The Context instance.

        Returns:
            Order: The cancelled order.
        """
        raise NotImplementedError

    def get_open_orders(self, context, target_symbol=None):
        """
        Get open orders, optionally filtered by symbol.

        Args:
            context: The Context instance.
            target_symbol: Optional symbol filter.

        Returns:
            List[Order]: Open orders.
        """
        return context.get_open_orders(target_symbol=target_symbol)

    def get_transactions(self):
        """
        Get all recorded transactions.

        Returns:
            List[Transaction]: All recorded transactions.
        """
        return list(self._transactions)

    def record_transaction(self, transaction):
        """Record a transaction (fill)."""
        self._transactions.append(transaction)

    def clear_transactions(self):
        """Clear all recorded transactions."""
        self._transactions.clear()

    def prune_orders(self, context):
        """
        Clean up completed orders from tracking.
        Override for custom pruning logic.
        """
        pass


class DefaultBlotter(Blotter):
    """
    Pass-through blotter for live trading.

    Does not apply slippage or commission — orders are forwarded
    directly to the OrderService for execution through the
    configured OrderExecutor.

    This is the default blotter used when no custom blotter is
    configured.

    Usage::

        app.set_blotter(DefaultBlotter())
    """

    def place_order(self, order_data, context):
        """
        Place an order directly through the order service.

        Args:
            order_data: Dict with order parameters (as built by Context).
            context: The Context instance.

        Returns:
            Order: The created order.
        """
        execute = order_data.pop("_execute", True)
        validate = order_data.pop("_validate", True)
        sync = order_data.pop("_sync", True)
        return context.order_service.create(
            order_data, execute=execute, validate=validate, sync=sync
        )

    def cancel_order(self, order_id, context):
        """
        Cancel a specific order by delegating to the OrderService.

        In live trading, this communicates with the exchange to
        cancel the order. In backtesting, it updates the order
        status directly.

        Args:
            order_id: The ID of the order to cancel.
            context: The Context instance.

        Returns:
            Order: The cancelled order.
        """
        from investing_algorithm_framework.domain.exceptions \
            import OperationalException

        order = context.order_service.get(order_id)

        if order is None:
            raise OperationalException(
                f"Order with id {order_id} not found"
            )

        context.order_service.cancel_order(order)
        return context.order_service.get(order_id)


class SimulationBlotter(Blotter):
    """
    Default blotter for backtesting with configurable slippage
    and commission models.

    Applies slippage to order prices and calculates commission
    fees, recording each fill as a Transaction for audit purposes.

    Usage::

        from investing_algorithm_framework import (
            SimulationBlotter, PercentageSlippage, PercentageCommission
        )

        app.set_blotter(SimulationBlotter(
            slippage_model=PercentageSlippage(0.001),   # 0.1%
            commission_model=PercentageCommission(0.001) # 0.1%
        ))
    """

    def __init__(
        self,
        slippage_model=None,
        commission_model=None,
    ):
        super().__init__()
        self.slippage_model = slippage_model or NoSlippage()
        self.commission_model = commission_model or NoCommission()

    def place_order(self, order_data, context):
        """
        Place an order with slippage and commission applied.

        For limit orders, slippage is applied to the order price.
        Commission is calculated and stored on the order.
        A Transaction is recorded for audit purposes.

        Args:
            order_data: Dict with order parameters (as built by Context,
                with amounts already resolved).
            context: The Context instance.

        Returns:
            Order: The created order.
        """
        order_side = order_data.get("order_side")
        price = order_data.get("price")
        original_price = price

        # Apply slippage to price for limit orders
        if price is not None and price > 0:
            slipped_price = self.slippage_model.calculate_slippage(
                price, order_side, order_data.get("amount")
            )
            order_data["price"] = slipped_price

        # Extract flow control params before passing to order_service
        execute = order_data.pop("_execute", True)
        validate = order_data.pop("_validate", True)
        sync = order_data.pop("_sync", True)

        # Create order through order service directly
        order = context.order_service.create(
            order_data, execute=execute, validate=validate, sync=sync
        )

        # Calculate commission
        fill_price = order.get_price()
        fill_amount = order.get_amount()
        commission = self.commission_model.calculate_commission(
            fill_price, fill_amount, order_side
        )

        # Update order with fee info
        if commission > 0:
            order.set_order_fee(commission)

        # Calculate slippage amount
        if original_price is not None and original_price > 0:
            slippage_amount = abs(fill_price - original_price)
        else:
            slippage_amount = 0

        # Record transaction
        self.record_transaction(Transaction(
            order_id=order.get_id(),
            symbol=order.get_symbol(),
            order_side=order.get_order_side(),
            price=fill_price,
            amount=fill_amount,
            cost=fill_price * fill_amount,
            commission=commission,
            slippage=slippage_amount,
        ))

        return order

    def cancel_order(self, order_id, context):
        """
        Cancel a specific order by delegating to the OrderService.

        In backtesting, applies any configured models before
        cancellation.

        Args:
            order_id: The ID of the order to cancel.
            context: The Context instance.

        Returns:
            Order: The cancelled order.
        """
        from investing_algorithm_framework.domain.exceptions \
            import OperationalException

        order = context.order_service.get(order_id)

        if order is None:
            raise OperationalException(
                f"Order with id {order_id} not found"
            )

        context.order_service.cancel_order(order)
        return context.order_service.get(order_id)
