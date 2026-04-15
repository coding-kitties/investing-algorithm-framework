import logging
from datetime import datetime, timezone
from queue import PriorityQueue
from typing import Union

from investing_algorithm_framework.domain import OrderStatus, TradeStatus, \
    Trade, OperationalException, OrderType, TradeTakeProfit, \
    TradeStopLoss, OrderSide, Environment, ENVIRONMENT, PeekableQueue, \
    DataType, INDEX_DATETIME, random_number, random_string
from investing_algorithm_framework.services.repository_service import \
    RepositoryService

logger = logging.getLogger(__name__)


def _safe_order_fee(order):
    """Safely get order_fee, avoiding SQLAlchemy detached-instance errors."""
    try:
        fee = getattr(order, 'order_fee', None)
        return fee if fee else 0
    except Exception:
        return 0


def _safe_buy_order(trade):
    """Safely get buy_order from a trade, avoiding lazy-load errors."""
    try:
        return getattr(trade, 'buy_order', None)
    except Exception:
        return None


def _get_buy_fee_portion(trade, portion_amount):
    """Get proportional buy fee for *portion_amount* of the trade."""
    buy_order = _safe_buy_order(trade)
    fee = _safe_order_fee(buy_order) if buy_order else 0
    if fee and trade.amount:
        return fee * (portion_amount / trade.amount)
    return 0


def _get_sell_fee_portion(sell_order, portion_amount):
    """Get proportional sell fee for *portion_amount* of the sell order."""
    fee = _safe_order_fee(sell_order)
    try:
        amount = sell_order.amount if sell_order else 0
    except Exception:
        amount = 0
    if fee and amount:
        return fee * (portion_amount / amount)
    return 0


class TradeService(RepositoryService):
    """
    Trade service class to handle trade related operations. This class
    is responsible for creating, updating, and deleting trades. It also
    takes care of keeping track of all sell transactions that are
    associated with a trade.

    Trade Allocation Pattern
    ~~~~~~~~~~~~~~~~~~~~~~~~
    Trades and sell orders have a many-to-many relationship: one sell
    order can close multiple trades (FIFO), and one trade can be
    partially closed by multiple sell orders. The TradeAllocation table
    acts as the allocation ledger — each record captures how much of a
    sell order was allocated to close a specific trade, along with the
    prices, fees, and net_gain contribution at time of creation.

    There are two creation paths for these allocation records:

    - **Path 1** (`_create_trade_allocations_fifo`): The sell
      order is matched to open trades automatically via a FIFO priority
      queue. Used when no explicit trade list is provided.
    - **Path 2** (`_create_trade_allocations_explicit`):
      The caller specifies exactly which trades (and amounts) the sell
      order should close. Used by stop-loss / take-profit flows.

    Both paths delegate per-allocation accounting to a single shared
    method (`_allocate_sell_to_trade`) which computes proportional fees,
    net_gain contribution, updates trade state, and persists the
    allocation record with all derived values stored.

    The allocation records also enable **cancellation reversal**
    (`update_trade_with_removed_sell_order`): when a sell order is
    cancelled, expired, or rejected, the stored `net_gain_contribution`,
    `buy_fee`, `sell_fee`, and `amount_pending` on each allocation
    record are used to restore trade state — no re-derivation needed.
    """

    def __init__(
        self,
        trade_repository,
        order_repository,
        trade_stop_loss_repository,
        trade_take_profit_repository,
        position_repository,
        portfolio_repository,
        configuration_service,
        trade_allocation_repository
    ):
        super(TradeService, self).__init__(trade_repository)
        self.order_repository = order_repository
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.configuration_service = configuration_service
        self.trade_stop_loss_repository = trade_stop_loss_repository
        self.trade_take_profit_repository = trade_take_profit_repository
        self.trade_allocation_repository = trade_allocation_repository

    def create_trade_from_buy_order(self, buy_order) -> Union[Trade, None]:
        """
        Function to create a trade from a buy order. If the given buy
        order has its status set to CANCELED, EXPIRED, or REJECTED,
        the trade object will not be created. If the given buy
        order has its status set to CLOSED or OPEN, the trade object
        will be created. The amount will be set to the filled amount.

        Args:
            buy_order: Order object representing the buy order

        Returns:
            Union[Trade, None] Representing the created trade object or None
        """

        if buy_order.status in \
                [
                    OrderStatus.CANCELED.value,
                    OrderStatus.EXPIRED.value,
                    OrderStatus.REJECTED.value
                ]:
            return None

        data = {
            "buy_order": buy_order,
            "target_symbol": buy_order.target_symbol,
            "trading_symbol": buy_order.trading_symbol,
            "amount": buy_order.get_amount(),
            "available_amount": buy_order.get_filled(),
            "filled_amount": buy_order.get_filled(),
            "remaining": buy_order.get_remaining(),
            "opened_at": buy_order.created_at,
            "cost": buy_order.get_filled() * buy_order.price
        }

        if buy_order.get_filled() > 0:
            data["status"] = TradeStatus.OPEN.value
            data["cost"] = buy_order.filled * buy_order.price

        return self.create(data)

    def _allocate_sell_to_trade(
        self, trade_id, sell_order, amount_to_close
    ):
        """
        Core allocation method — creates a single TradeAllocation record
        linking a sell order to a trade for the given amount, computes
        fees and net_gain, updates the trade, and stores everything on
        the allocation record.

        Both Path 1 (FIFO) and Path 2 (explicit trades) delegate here.

        Args:
            trade_id: int, the id of the trade to (partially) close
            sell_order: Sell order providing the close price
            amount_to_close: float, the amount being closed on this trade

        Returns:
            The created allocation record
        """
        trade = self.get(trade_id)
        open_price = trade.open_price
        sell_price = sell_order.price
        sell_order_id = sell_order.id
        sell_updated_at = sell_order.updated_at
        current_available = trade.available_amount
        current_net_gain = trade.net_gain
        current_filled = trade.filled_amount
        current_amount = trade.amount

        buy_fee = _get_buy_fee_portion(trade, amount_to_close)
        sell_fee = _get_sell_fee_portion(sell_order, amount_to_close)
        cost = open_price * amount_to_close
        net_gain = (sell_price * amount_to_close) - cost - buy_fee - sell_fee

        # Create the allocation record with all derived values stored
        allocation = self.trade_allocation_repository.create({
            "order_id": sell_order_id,
            "trade_id": trade_id,
            "amount": amount_to_close,
            "amount_pending": amount_to_close,
            "open_price": open_price,
            "close_price": sell_price,
            "buy_fee": buy_fee,
            "sell_fee": sell_fee,
            "net_gain_contribution": net_gain,
        })

        # Re-fetch trade after DB operation to avoid detached instance
        trade = self.get(trade_id)

        # Link the sell order to the trade
        sell_order = self.order_repository.get(sell_order_id)
        self.repository.add_order_to_trade(trade, sell_order)

        # Update trade state
        new_available = current_available - amount_to_close
        update_data = {
            "available_amount": new_available,
            "updated_at": sell_updated_at,
            "net_gain": current_net_gain + net_gain,
        }

        # A trade is CLOSED only when all amount is sold
        # (available == 0) and the buy order is fully filled
        # (filled_amount == amount).
        if new_available == 0 and current_filled == current_amount:
            update_data["closed_at"] = sell_updated_at
            update_data["status"] = TradeStatus.CLOSED.value
        elif new_available == 0:
            # All available sold but buy order not fully filled
            update_data["closed_at"] = sell_updated_at

        self.update(trade_id, update_data)
        return allocation

    def _create_trade_allocations_fifo(self, sell_order):
        """
        Path 1 — FIFO auto-match.

        Matches the sell order against open trades in FIFO order
        (oldest first via PriorityQueue) and delegates each allocation
        to `_allocate_sell_to_trade`.

        Used when the caller does not specify which trades to close
        (i.e. a plain sell order from the strategy).

        Args:
            sell_order: Order object representing the sell order

        Returns:
            None
        """
        position = self.position_repository.find({
            "order_id": sell_order.id
        })
        portfolio_id = position.portfolio_id
        matching_trades = self.get_all({
            "status": TradeStatus.OPEN.value,
            "target_symbol": sell_order.target_symbol,
            "portfolio_id": portfolio_id
        })
        total_available_to_close = 0
        amount_to_close = sell_order.amount
        trade_queue = PriorityQueue()

        for trade in matching_trades:
            if trade.available_amount > 0:
                total_available_to_close += trade.available_amount
                trade_queue.put(trade)

        if total_available_to_close < amount_to_close:
            raise OperationalException(
                "Not enough amount to close in trades."
            )

        while amount_to_close > 0 and not trade_queue.empty():
            trade = trade_queue.get()
            available_to_close = trade.available_amount
            close_amount = min(amount_to_close, available_to_close)
            self._allocate_sell_to_trade(
                trade.id, sell_order, close_amount
            )
            amount_to_close -= close_amount

    def _create_stop_loss_allocation_with_sell_order(
        self, sell_order_id, stop_losses
    ):
        """
        Create allocation records linking a sell order to stop-losses.
        """
        sell_order = self.order_repository.get(sell_order_id)

        for stop_loss_data in stop_losses:

            self.trade_allocation_repository.\
                create({
                    "order_id": sell_order.id,
                    "stop_loss_id": stop_loss_data["stop_loss_id"],
                    "amount": stop_loss_data["amount"],
                    "amount_pending": stop_loss_data["amount"]
                })

    def _create_take_profit_allocation_with_sell_order(
        self, sell_order_id, take_profits
    ):
        """
        Create allocation records linking a sell order to take-profits.
        """
        sell_order = self.order_repository.get(sell_order_id)

        for take_profit_data in take_profits:

            self.trade_allocation_repository.\
                create({
                    "order_id": sell_order.id,
                    "take_profit_id": take_profit_data["take_profit_id"],
                    "amount": take_profit_data["amount"],
                    "amount_pending": take_profit_data["amount"]
                })

    def update(self, trade_id, data) -> Trade:
        """
        Function to update a trade object. This function will update
        the trade object with the given data.

        Args:
            trade_id: int representing the id of the trade object
            data: dict representing the data that should be updated

        Returns:
            Trade object
        """

        # Update the stop losses and take profits if last reported price
        # is updated
        if "last_reported_price" in data:
            trade = self.get(trade_id)
            stop_losses = trade.stop_losses
            to_be_saved_stop_losses = []
            take_profits = trade.take_profits
            to_be_saved_take_profits = []

            # Check if 'update_at' attribute is in data

            if 'last_reported_price_date' in data:
                last_reported_price_date = data["last_reported_price_date"]
            else:

                # Check if config environment has value BACKTEST
                config = self.configuration_service.get_config()
                environment = config[ENVIRONMENT]

                if Environment.BACKTEST.equals(environment):
                    last_reported_price_date = \
                        config[INDEX_DATETIME]
                else:
                    last_reported_price_date = \
                        datetime.now(tz=timezone.utc)

            for stop_loss in stop_losses:

                if stop_loss.active:
                    stop_loss.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_stop_losses.append(stop_loss)

            for take_profit in take_profits:

                if take_profit.active:
                    take_profit.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_take_profits.append(take_profit)

            self.trade_stop_loss_repository\
                .save_objects(to_be_saved_stop_losses)

            self.trade_take_profit_repository\
                .save_objects(to_be_saved_take_profits)

        return super(TradeService, self).update(trade_id, data)

    def _create_trade_allocations_explicit(
        self, sell_order, trades
    ):
        """
        Path 2 — Explicit trade list.

        Creates allocation records for a sell order using a caller-
        supplied list of trades and amounts. Each entry in `trades` is
        a dict with `trade_id` and `amount`. This path is used by
        stop-loss and take-profit flows where the exact trade-to-order
        mapping is already known.

        Delegates per-allocation accounting to `_allocate_sell_to_trade`.
        """

        for trade_data in trades:
            self._allocate_sell_to_trade(
                trade_data["trade_id"], sell_order, trade_data["amount"]
            )

    def create_trade_allocations(
        self, sell_order, trades=None, stop_losses=None, take_profits=None
    ):
        """
        Create trade allocation records for a sell order, update the
        associated trades, position cost, and portfolio net_gain.

        If only the sell order is provided, FIFO matching is used. If
        trades/stop_losses/take_profits are provided, explicit matching
        is used.

        After creating the allocation records, this method reads back
        the stored fees and net_gain_contribution to update the position
        and portfolio — no re-derivation needed.

        Args:
            sell_order: Order object representing the sell order that has
                been created
            trades: List of dicts with trade_id/amount. Default is None.
            stop_losses: List of dicts with stop_loss_id/amount. Default
                is None.
            take_profits: List of dicts with take_profit_id/amount.
                Default is None.

        Returns:
            None
        """
        sell_order_id = sell_order.id
        sell_price = sell_order.price
        sell_amount = sell_order.amount

        if (trades is None or len(trades) == 0) \
                and (stop_losses is None or len(stop_losses) == 0) \
                and (take_profits is None or len(take_profits) == 0):
            self._create_trade_allocations_fifo(sell_order)
        else:

            if stop_losses is not None:
                self._create_stop_loss_allocation_with_sell_order(
                    sell_order_id, stop_losses
                )

            if take_profits is not None:
                self._create_take_profit_allocation_with_sell_order(
                    sell_order_id, take_profits
                )

            if trades is not None:
                self._create_trade_allocations_explicit(
                    sell_order, trades
                )

        # Retrieve all allocation records for this sell order
        allocations = self.trade_allocation_repository.get_all({
            "order_id": sell_order_id
        })

        # Update the position cost using stored values
        position = self.position_repository.find({
            "order_id": sell_order_id
        })

        cost = 0
        net_gain = 0

        for allocation in allocations:
            if allocation.trade_id is not None:
                cost += allocation.open_price * allocation.amount
                net_gain += allocation.net_gain_contribution

        position.cost -= cost
        self.position_repository.save(position)

        # Update the net gain, net size of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain += net_gain
        portfolio.net_size += net_gain
        portfolio.total_revenue += sell_price * sell_amount
        self.portfolio_repository.save(portfolio)

    def update_trade_with_removed_sell_order(
        self, sell_order
    ) -> Trade:
        """
        Cancellation reversal — undo the effect of a sell order.

        When a sell order is cancelled, expired, or rejected, this
        method reads the stored values from each TradeAllocation record
        to restore each affected trade to its pre-sell state:

        - `available_amount` is increased by the allocated amount.
        - `net_gain` is decreased by the stored `net_gain_contribution`.
        - Trade status is set back to OPEN.
        - Associated stop-loss / take-profit sold_amounts are reversed.
        - Position cost and portfolio net_gain / net_size are restored.

        Because fees and net_gain are stored on the allocation record
        at creation time, no re-derivation is needed — eliminating
        the risk of calculation mismatches.

        Args:
            sell_order (Order): Order object representing the sell order
                that has been removed

        Returns:
            Trade: Trade object representing the updated trade object
        """
        position_cost = 0
        total_net_gain = 0

        # Get all allocation records for this sell order
        allocations = self.trade_allocation_repository.get_all({
            "order_id": sell_order.id
        })

        for allocation in allocations:
            # If trade id is not None, update the trade object
            if allocation.trade_id is not None:
                trade = self.get(allocation.trade_id)
                cost = allocation.amount_pending * allocation.open_price

                # Scale the stored net_gain_contribution proportionally
                # to the unfilled (pending) portion. If the order was
                # partially filled before cancellation, only reverse
                # the unfilled part.
                if allocation.amount and allocation.amount > 0:
                    pending_ratio = (
                        allocation.amount_pending / allocation.amount
                    )
                else:
                    pending_ratio = 1
                net_gain = allocation.net_gain_contribution * pending_ratio

                trade.available_amount += allocation.amount_pending
                trade.status = TradeStatus.OPEN.value
                trade.updated_at = sell_order.updated_at
                trade.net_gain -= net_gain
                trade.cost += cost
                trade = self.save(trade)

                # Update the position cost
                position_cost += cost
                total_net_gain += net_gain

            if allocation.stop_loss_id is not None:
                stop_loss = self.trade_stop_loss_repository\
                    .get(allocation.stop_loss_id)
                stop_loss.sold_amount -= allocation.amount_pending
                stop_loss.remove_sell_price(
                    sell_order.price, sell_order.created_at
                )

                if stop_loss.sold_amount < stop_loss.sell_amount:
                    stop_loss.active = True
                    stop_loss.high_water_mark = None

                self.trade_stop_loss_repository.save(stop_loss)

            if allocation.take_profit_id is not None:
                take_profit = self.trade_take_profit_repository\
                    .get(allocation.take_profit_id)
                take_profit.sold_amount -= allocation.amount_pending
                take_profit.remove_sell_price(
                    sell_order.price, sell_order.created_at
                )

                if take_profit.sold_amount < take_profit.sell_amount:
                    take_profit.active = True
                    take_profit.high_water_mark = None

                self.trade_take_profit_repository.save(take_profit)

        # Update the position cost
        position = self.position_repository.find({
            "order_id": sell_order.id
        })
        position.cost += position_cost
        self.position_repository.save(position)

        # Update the net gain of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain -= total_net_gain
        portfolio.net_size -= total_net_gain
        self.portfolio_repository.save(portfolio)
        return trade

    def update_trade_with_buy_order(
        self, filled_difference, buy_order
    ) -> Trade:
        """
        Function to update a trade from a buy order. This function
        checks if a trade exists for the buy order. If the given buy
        order has its status set to CANCLED, EXPIRED, or REJECTED, the
        trade will object will be removed. If the given buy order has
        its status set to CLOSED or OPEN, the amount and
        remaining of the trade object will be updated.

        Args:
            filled_difference: float representing the difference between the
                filled amount of the buy order and the filled amount
                of the trade
            buy_order: Order object representing the buy order

        Returns:
            Trade object
        """
        trade = self.find({"buy_order": buy_order.id})
        filled = buy_order.get_filled()
        amount = buy_order.get_amount()

        if filled is None:
            filled = trade.filled_amount + filled_difference

        remaining = buy_order.get_remaining()

        if remaining is None:
            remaining = trade.remaining - filled_difference

        if trade is None:
            raise OperationalException(
                "Trade does not exist for buy order."
            )

        status = buy_order.get_status()

        if status in \
                [
                    OrderStatus.CANCELED.value,
                    OrderStatus.EXPIRED.value,
                    OrderStatus.REJECTED.value
                ]:
            return self.delete(trade.id)

        trade = self.find({"order_id": buy_order.id})
        updated_data = {
            "available_amount": trade.available_amount + filled_difference,
            "filled_amount": filled,
            "remaining": remaining,
            "cost": trade.cost + filled_difference * buy_order.price
        }

        if amount != trade.amount:
            updated_data["amount"] = amount
            updated_data["cost"] = amount * buy_order.price

        if filled_difference > 0:
            updated_data["status"] = TradeStatus.OPEN.value

        trade = self.update(trade.id, updated_data)
        return trade

    def update_trade_with_filled_sell_order(
        self, filled_difference, sell_order
    ) -> Trade:
        """
        Function to update a trade with a filled sell order. This
        function will update all the metadata objects that where
        created by the sell order.

        Args:
            filled_difference: float representing the difference between
                the filled amount of the sell order and the filled amount
                of the trade
            sell_order: Order object representing the sell order

        Returns:
            Trade object
        """
        # Update all allocation records
        allocations = self.trade_allocation_repository.get_all({
            "order_id": sell_order.id
        })

        trade_filled_difference = filled_difference
        stop_loss_filled_difference = filled_difference
        take_profit_filled_difference = filled_difference
        total_amount_in_allocations = 0
        trade_allocations = []

        for allocation in allocations:
            # Update the trade allocation
            if allocation.trade_id is not None \
                    and trade_filled_difference > 0:

                trade_allocations.append(allocation)
                total_amount_in_allocations += allocation.amount

                if allocation.amount_pending >= trade_filled_difference:
                    amount = trade_filled_difference
                    trade_filled_difference = 0
                else:
                    amount = allocation.amount_pending
                    trade_filled_difference -= amount

                allocation.amount_pending -= amount
                self.trade_allocation_repository.save(allocation)

            if allocation.stop_loss_id is not None \
                    and stop_loss_filled_difference > 0:

                if (
                    allocation.amount_pending >=
                    stop_loss_filled_difference
                ):
                    amount = stop_loss_filled_difference
                    stop_loss_filled_difference = 0
                else:
                    amount = allocation.amount_pending
                    stop_loss_filled_difference -= amount

                allocation.amount_pending -= amount
                self.trade_allocation_repository.save(allocation)

            if allocation.take_profit_id is not None \
                    and take_profit_filled_difference > 0:

                if (
                    allocation.amount_pending >=
                    take_profit_filled_difference
                ):
                    amount = take_profit_filled_difference
                    take_profit_filled_difference = 0
                else:
                    amount = allocation.amount_pending
                    take_profit_filled_difference -= amount

                allocation.amount_pending -= amount
                self.trade_allocation_repository.save(allocation)

        # Update trade available amount if the total amount in allocations
        # is not equal to the sell order amount
        if total_amount_in_allocations != sell_order.amount:
            difference = sell_order.amount - total_amount_in_allocations
            trades = []

            for allocation in trade_allocations:
                trade = self.get(allocation.trade_id)
                trades.append(trade)

            # Sort trades by created_at with the most recent first
            trades = sorted(
                trades,
                key=lambda x: x.updated_at,
                reverse=True
            )
            queue = PeekableQueue(trades)

            while difference != 0 and not queue.is_empty():
                trade = queue.dequeue()
                trade.available_amount -= difference
                self.save(trade)

    def update_trades_with_market_data(self, market_data):
        """
        Function to update trades with market data. This function will
        update the last reported price and last reported price date of the
        trade.

        Args:
            market_data: dict representing the market data
                that will be used to update the trades

        Returns:
            None
        """
        open_trades = self.get_all({"status": TradeStatus.OPEN.value})
        meta_data = market_data["metadata"]

        for open_trade in open_trades:
            ohlcv_meta_data = meta_data[DataType.OHLCV]

            if open_trade.symbol not in ohlcv_meta_data:
                continue

            timeframes = ohlcv_meta_data[open_trade.symbol].keys()
            sorted_timeframes = sorted(timeframes)
            most_granular_interval = sorted_timeframes[0]
            identifier = (
                ohlcv_meta_data[open_trade.symbol][most_granular_interval]
            )
            data = market_data[identifier]

            # Get last row of data
            last_row = data.tail(1)
            update_data = {
                "last_reported_price": last_row["Close"][0],
                "last_reported_price_datetime": last_row["Datetime"][0],
                "updated_at": last_row["Datetime"][0]
            }
            self.update(open_trade.id, update_data)

    def add_stop_loss(
        self,
        trade,
        percentage: float,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: datetime = None
    ) -> TradeStopLoss:
        """
        Function to add a stop loss to a trade.

        Example of fixed stop loss:
            * You buy BTC at $40,000.
            * You set a SL of 5% → SL level at $38,000 (40,000 - 5%).
            * BTC price increases to $42,000 → SL level remains at $38,000.
            * BTC price drops to $38,000 → SL level reached, trade closes.

        Example of trailing stop loss:
            * You buy BTC at $40,000.
            * You set a TSL of 5%, setting the sell price at $38,000.
            * BTC price increases to $42,000 → New TSL level at
                $39,900 (42,000 - 5%).
            * BTC price drops to $39,900 → SL level reached, trade closes.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trailing (bool): representing whether the stop loss is a
                trailing stop loss or not. Default is False.
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered.
            created_at: datetime representing the creation date of the
                stop loss. If None, the current datetime will be used.

        Returns:
            None
        """
        trade = self.get(trade.id)

        # Check if the sell percentage + the existing stop losses is
        # greater than 100
        existing_sell_percentage = 0
        for stop_loss in trade.stop_losses:
            existing_sell_percentage += stop_loss.sell_percentage

        if existing_sell_percentage + sell_percentage > 100:
            raise OperationalException(
                "Combined sell percentages of stop losses belonging "
                "to trade exceeds 100."
            )

        creation_data = {
            "trade_id": trade.id,
            "trailing": trailing,
            "percentage": percentage,
            "open_price": trade.open_price,
            "total_amount_trade": trade.amount,
            "sell_percentage": sell_percentage,
            "active": True,
            "created_at": created_at if created_at is not None
            else datetime.now(tz=timezone.utc)
        }
        return self.trade_stop_loss_repository.create(creation_data)

    def add_take_profit(
        self,
        trade,
        percentage: float,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: datetime = None
    ) -> TradeTakeProfit:
        """
        Function to add a take profit to a trade. This function will add a
        take profit to the specified trade. If the take profit is triggered,
        the trade will be closed.

        Example of take profit:
            * You buy BTC at $40,000.
            * You set a TP of 5% → TP level at $42,000 (40,000 + 5%).
            * BTC rises to $42,000 → TP level reached, trade
                closes, securing profit.

        Example of trailing take profit:
            * You buy BTC at $40,000
            * You set a TTP of 5%, setting the sell price at $42,000.
            * BTC rises to $42,000 → TTP level stays at $42,000.
            * BTC rises to $45,000 → New TTP level at $42,750.
            * BTC drops to $42,750 → Trade closes, securing profit.

        Args:
            trade: Trade object representing the trade
            percentage (float): representing the percentage of the open price
                that the stop loss should be set at. This must be a positive
                number, e.g. 5 for 5%, or 10 for 10%.
            trailing (bool): representing whether the take profit is a
                trailing take profit or not. Default is False.
            sell_percentage (float): representing the percentage of the trade
                that should be sold if the stop loss is triggered
            created_at (datetime): datetime representing the creation
                date of the take profit. If None, the current datetime
                will be used.

        Returns:
            None
        """
        trade = self.get(trade.id)

        # Check if the sell percentage + the existing stop losses is
        # greater than 100
        existing_sell_percentage = 0
        for take_profit in trade.take_profits:
            existing_sell_percentage += take_profit.sell_percentage

        if existing_sell_percentage + sell_percentage > 100:
            raise OperationalException(
                "Combined sell percentages of stop losses belonging "
                "to trade exceeds 100."
            )
        creation_data = {
            "trade_id": trade.id,
            "trailing": trailing,
            "percentage": percentage,
            "open_price": trade.open_price,
            "total_amount_trade": trade.amount,
            "sell_percentage": sell_percentage,
            "active": True,
            "created_at": created_at if created_at is not None
            else datetime.now(tz=timezone.utc)
        }
        return self.trade_take_profit_repository.create(creation_data)

    def get_triggered_stop_loss_orders(self):
        """
        Function to get all triggered stop loss orders. This function will
        return a list of trade ids that have triggered stop losses.

        Returns:
            List of trade ids
        """
        sell_orders_data = []
        query = {"status": TradeStatus.OPEN.value}
        open_trades = self.get_all(query)
        to_be_saved_stop_loss_objects = []

        # Group trades by target symbol
        stop_losses_by_target_symbol = {}

        for open_trade in open_trades:
            triggered_stop_losses = []

            for stop_loss in open_trade.stop_losses:

                if (
                    stop_loss.active
                    and stop_loss.has_triggered(open_trade.last_reported_price)
                ):
                    triggered_stop_losses.append(stop_loss)

                to_be_saved_stop_loss_objects.append(stop_loss)

            if len(triggered_stop_losses) > 0:
                stop_losses_by_target_symbol[open_trade] = \
                    triggered_stop_losses

        for trade in stop_losses_by_target_symbol:
            stop_losses = stop_losses_by_target_symbol[trade]
            available_amount = trade.available_amount
            stop_loss_que = PeekableQueue(stop_losses)
            order_amount = 0
            stop_loss_metadata = []

            # While there is an available amount and there are stop losses
            # to process
            while not stop_loss_que.is_empty() and available_amount > 0:
                stop_loss = stop_loss_que.dequeue()
                stop_loss_sell_amount = stop_loss.get_sell_amount()

                if stop_loss_sell_amount <= available_amount:
                    available_amount = available_amount - stop_loss_sell_amount
                    stop_loss.active = False
                    stop_loss.sold_amount += stop_loss_sell_amount
                    order_amount += stop_loss_sell_amount
                else:
                    stop_loss.sold_amount += available_amount

                    # Deactivate stop loss if the filled amount is equal
                    # to the amount of the trade, meaning that there is
                    # nothing left to sell
                    if trade.filled_amount == trade.amount:
                        stop_loss.active = False
                    else:
                        stop_loss.active = True

                    order_amount += available_amount
                    stop_loss_sell_amount = available_amount
                    available_amount = 0

                stop_loss_metadata.append({
                    "stop_loss_id": stop_loss.id,
                    "amount": stop_loss_sell_amount
                })
                stop_loss.add_sell_price(
                    trade.last_reported_price,
                    trade.last_reported_price_datetime
                )

            position = self.position_repository.find({
                "order_id": trade.orders[0].id
            })
            portfolio_id = position.portfolio_id
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio_id,
                    "stop_losses": stop_loss_metadata,
                    "trades": [{
                        "trade_id": trade.id,
                        "amount": order_amount
                    }]
                }
            )

        self.trade_stop_loss_repository\
            .save_objects(to_be_saved_stop_loss_objects)
        return sell_orders_data

    def get_triggered_take_profit_orders(self):
        """
        Function to get all triggered stop loss orders. This function will
        return a list of trade ids that have triggered stop losses.

        Returns:
            List of trade objects. A trade object is a dictionary
        """
        sell_orders_data = []
        query = {"status": TradeStatus.OPEN.value}
        open_trades = self.get_all(query)
        to_be_saved_take_profit_objects = []

        # Group trades by target symbol
        take_profits_by_target_symbol = {}

        for open_trade in open_trades:
            triggered_take_profits = []
            available_amount = open_trade.available_amount

            # Skip if there is no available amount
            if available_amount == 0:
                continue

            for take_profit in open_trade.take_profits:
                if (
                    take_profit.active and
                    take_profit.has_triggered(open_trade.last_reported_price)
                ):
                    triggered_take_profits.append(take_profit)

                to_be_saved_take_profit_objects.append(take_profit)

            if len(triggered_take_profits) > 0:
                take_profits_by_target_symbol[open_trade] = \
                    triggered_take_profits

        for trade in take_profits_by_target_symbol:
            take_profits = take_profits_by_target_symbol[trade]
            available_amount = trade.available_amount
            take_profit_que = PeekableQueue(take_profits)
            order_amount = 0
            take_profit_metadata = []

            # While there is an available amount and there are take profits
            # to process
            while not take_profit_que.is_empty() and available_amount > 0:
                take_profit = take_profit_que.dequeue()
                take_profit_sell_amount = take_profit.get_sell_amount()

                if take_profit_sell_amount <= available_amount:
                    available_amount = available_amount - \
                        take_profit_sell_amount
                    take_profit.active = False
                    take_profit.sold_amount += take_profit_sell_amount
                    order_amount += take_profit_sell_amount
                else:
                    take_profit.sold_amount += available_amount

                    # Deactivate take profit if the filled amount is equal
                    # to the amount of the trade, meaning that there is
                    # nothing left to sell
                    if trade.filled_amount == trade.amount:
                        take_profit.active = False
                    else:
                        take_profit.active = True

                    order_amount += available_amount
                    take_profit_sell_amount = available_amount
                    available_amount = 0

                take_profit_metadata.append({
                    "take_profit_id": take_profit.id,
                    "amount": take_profit_sell_amount
                })

                take_profit.add_sell_price(
                    trade.last_reported_price,
                    trade.last_reported_price_datetime
                )

            position = self.position_repository.find({
                "order_id": trade.orders[0].id
            })
            portfolio_id = position.portfolio_id
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio_id,
                    "take_profits": take_profit_metadata,
                    "trades": [{
                        "trade_id": trade.id,
                        "amount": order_amount
                    }]
                }
            )

        self.trade_take_profit_repository\
            .save_objects(to_be_saved_take_profit_objects)
        return sell_orders_data

    def _create_order_id(self) -> str:
        """
        Function to create a unique order id. This function will
        create a unique order id based on the current time and
        the order id counter.

        Returns:
            str: Unique order id
        """
        unique = False
        order_id = None

        while not unique:
            order_id = f"{random_number(8)}-{random_string(8)}"

            if not self.exists({"order_id": order_id}):
                unique = True

        return order_id
