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
    def calculate_slippage(
        self, price, order_side, amount=None, volume=None
    ):
        """
        Calculate the slipped execution price.

        Args:
            price: The intended fill price
            order_side: The side of the order ('BUY' or 'SELL')
            amount: The order amount (for volume-based models)
            volume: Available market volume (for impact models)

        Returns:
            float: The adjusted price after slippage
        """
        raise NotImplementedError


class NoSlippage(SlippageModel):
    """No slippage — fills at the exact order price."""

    def calculate_slippage(
        self, price, order_side, amount=None, volume=None
    ):
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

    def calculate_slippage(
        self, price, order_side, amount=None, volume=None
    ):
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

    def calculate_slippage(
        self, price, order_side, amount=None, volume=None
    ):
        from investing_algorithm_framework.domain.models.order.order_side \
            import OrderSide

        if OrderSide.BUY.equals(order_side):
            return price + self.amount
        else:
            return price - self.amount


class VolumeImpactSlippage(SlippageModel):
    """
    Volume-based market impact slippage model.

    Slippage increases with order size relative to available volume
    using a power-law model:

        impact = base_percentage * (amount / volume) ^ impact_power

    Buy orders fill higher, sell orders fill lower. When volume
    data is unavailable, falls back to base_percentage as flat
    slippage.

    Usage::

        VolumeImpactSlippage(
            base_percentage=0.001,  # 0.1% base
            impact_power=0.5        # square-root impact
        )
    """

    def __init__(self, base_percentage=0.001, impact_power=0.5):
        """
        Args:
            base_percentage: Base slippage as a decimal (0.001 = 0.1%).
            impact_power: Exponent for the participation rate.
                0.5 gives square-root impact (common in literature).
        """
        self.base_percentage = base_percentage
        self.impact_power = impact_power

    def calculate_slippage(
        self, price, order_side, amount=None, volume=None
    ):
        from investing_algorithm_framework.domain.models.order.order_side \
            import OrderSide

        if (
            volume is not None
            and volume > 0
            and amount is not None
            and amount > 0
        ):
            participation_rate = amount / volume
            impact = self.base_percentage * (
                participation_rate ** self.impact_power
            )
        else:
            impact = self.base_percentage

        if OrderSide.BUY.equals(order_side):
            return price * (1 + impact)
        else:
            return price * (1 - impact)


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


class FillModel(ABC):
    """
    Abstract base class for fill models.

    Fill models determine how much of an order can be filled
    in a single evaluation step. This enables partial fill
    simulation during backtesting.
    """

    @abstractmethod
    def get_fill_amount(self, order_amount, available_volume=None):
        """
        Calculate the fillable amount for this evaluation step.

        Args:
            order_amount: The remaining order amount to fill.
            available_volume: Available market volume for the
                current candle (None if unknown).

        Returns:
            float: The amount that can be filled (up to order_amount).
        """
        raise NotImplementedError


class FullFill(FillModel):
    """Fill the entire order immediately (default behavior)."""

    def get_fill_amount(self, order_amount, available_volume=None):
        return order_amount


class VolumeBasedFill(FillModel):
    """
    Volume-based partial fill model.

    Limits each fill to a fraction of the candle's traded volume,
    simulating realistic liquidity constraints. Orders larger than
    the available volume fraction remain partially open and are
    re-evaluated on subsequent candles.

    Usage::

        VolumeBasedFill(max_volume_fraction=0.1)  # max 10% of volume
    """

    def __init__(self, max_volume_fraction=0.1):
        """
        Args:
            max_volume_fraction: Maximum fraction of candle volume
                that can be filled per step (0.1 = 10%).
        """
        self.max_volume_fraction = max_volume_fraction

    def get_fill_amount(self, order_amount, available_volume=None):
        if available_volume is None or available_volume <= 0:
            return order_amount

        max_fill = available_volume * self.max_volume_fraction
        return min(order_amount, max_fill)


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

    # ------------------------------------------------------------------
    # Fill-time methods: used by the BacktestTradeOrderEvaluator
    # to calculate fill prices, fees, and amounts at the moment an
    # order is detected as filled.
    # ------------------------------------------------------------------

    def get_fill_price(
        self, base_price, order_side, amount=None, volume=None
    ):
        """
        Calculate the fill price after slippage.

        Called by the evaluator when an order fill is detected.
        Override for custom slippage behavior.

        Args:
            base_price: The base price (candle open for market
                orders, limit price for limit orders).
            order_side: The side of the order ('BUY' or 'SELL').
            amount: The fill amount.
            volume: Available candle volume (for impact models).

        Returns:
            float: The adjusted fill price.
        """
        return base_price

    def get_fill_commission(self, price, amount, order_side):
        """
        Calculate commission for a fill.

        Called by the evaluator when an order fill is detected.
        Override for custom fee models.

        Args:
            price: The fill price.
            amount: The fill amount.
            order_side: The side of the order.

        Returns:
            float: The commission amount.
        """
        return 0.0

    def get_fill_amount(self, order_amount, available_volume=None):
        """
        Calculate how much of an order can be filled.

        Override for partial fill behavior based on volume.

        Args:
            order_amount: The remaining order amount.
            available_volume: Available candle volume.

        Returns:
            float: The fillable amount (up to order_amount).
        """
        return order_amount

    def get_commission_rate(self):
        """
        Return the commission rate if applicable.

        Returns:
            float or None: The commission rate as a decimal,
                or None if not rate-based.
        """
        return None

    def on_fill(
        self, order_id, symbol, order_side,
        fill_price, base_price, fill_amount,
    ):
        """
        Called when an order fill is detected. Records a transaction
        and returns the commission.

        Args:
            order_id: The order ID.
            symbol: The symbol traded.
            order_side: The side of the order.
            fill_price: The actual fill price.
            base_price: The original base price before slippage.
            fill_amount: The amount filled.

        Returns:
            float: The commission amount.
        """
        commission = self.get_fill_commission(
            fill_price, fill_amount, order_side
        )
        slippage = abs(fill_price - base_price)
        self.record_transaction(Transaction(
            order_id=order_id,
            symbol=symbol,
            order_side=order_side,
            price=fill_price,
            amount=fill_amount,
            cost=fill_price * fill_amount,
            commission=commission,
            slippage=slippage,
        ))
        return commission


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
    Default blotter for backtesting with configurable slippage,
    commission, and fill models.

    Slippage and commission are applied at fill time (when the
    BacktestTradeOrderEvaluator detects a fill in OHLCV data),
    not at order creation time. This avoids double-counting and
    provides accurate fill tracking.

    Usage::

        from investing_algorithm_framework import (
            SimulationBlotter, PercentageSlippage,
            PercentageCommission, VolumeBasedFill
        )

        app.set_blotter(SimulationBlotter(
            slippage_model=PercentageSlippage(0.001),    # 0.1%
            commission_model=PercentageCommission(0.001), # 0.1%
            fill_model=VolumeBasedFill(0.1),  # max 10% of volume
        ))
    """

    def __init__(
        self,
        slippage_model=None,
        commission_model=None,
        fill_model=None,
    ):
        super().__init__()
        self.slippage_model = slippage_model or NoSlippage()
        self.commission_model = commission_model or NoCommission()
        self.fill_model = fill_model or FullFill()

    def place_order(self, order_data, context):
        """
        Place an order through the order service.

        Slippage and commission are NOT applied here — they are
        applied at fill time by the BacktestTradeOrderEvaluator
        using get_fill_price() and get_fill_commission().

        Args:
            order_data: Dict with order parameters.
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

    def get_fill_price(
        self, base_price, order_side, amount=None, volume=None
    ):
        """Calculate fill price using the configured slippage model."""
        return self.slippage_model.calculate_slippage(
            base_price, order_side, amount=amount, volume=volume
        )

    def get_fill_commission(self, price, amount, order_side):
        """Calculate commission using the configured commission model."""
        return self.commission_model.calculate_commission(
            price, amount, order_side
        )

    def get_fill_amount(self, order_amount, available_volume=None):
        """Calculate fillable amount using the configured fill model."""
        return self.fill_model.get_fill_amount(
            order_amount, available_volume
        )

    def get_commission_rate(self):
        """Return the commission rate if using PercentageCommission."""
        if hasattr(self.commission_model, 'percentage'):
            return self.commission_model.percentage
        return None

    def cancel_order(self, order_id, context):
        """
        Cancel a specific order by delegating to the OrderService.

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
