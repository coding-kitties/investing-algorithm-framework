import logging
from datetime import datetime, timezone
from queue import PriorityQueue
from typing import Union

from investing_algorithm_framework.domain import OrderStatus, TradeStatus, \
    Trade, OperationalException, OrderType, TradeTakeProfit, \
    TradeStopLoss, OrderSide, Environment, ENVIRONMENT, PeekableQueue, \
    DataType, INDEX_DATETIME, PositionMode, random_number, random_string
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
        trade_allocation_repository,
        trade_hook_dispatcher=None
    ):
        super(TradeService, self).__init__(trade_repository)
        self.order_repository = order_repository
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.configuration_service = configuration_service
        self.trade_stop_loss_repository = trade_stop_loss_repository
        self.trade_take_profit_repository = trade_take_profit_repository
        self.trade_allocation_repository = trade_allocation_repository
        self.trade_hook_dispatcher = trade_hook_dispatcher

    def _dispatch_trade_hook(self, hook_name, trade):
        """Best-effort notify the owning strategy of a trade-lifecycle
        event. No-op when no dispatcher is wired or no hook is active.
        """
        if self.trade_hook_dispatcher is not None and trade is not None:
            self.trade_hook_dispatcher.dispatch(hook_name, trade)

    def create_trade_at_fill(
        self, buy_order, fill_amount, fill_price, opened_at
    ) -> Union[Trade, None]:
        """
        Create a Trade row for a single fill event on a buy order.

        v9.0 (#431) — trades are no longer created eagerly when a buy
        order is placed. Instead, ``OrderService.update`` calls this
        method for every positive ``filled_difference`` it observes,
        producing one Trade per fill event. The position aggregates
        these trades.

        Any pending stop-loss / take-profit rules queued on the
        ``buy_order.metadata`` (via :meth:`Order.add_pending_stop_loss`
        / :meth:`Order.add_pending_take_profit`) are materialized onto
        the new trade before it is returned.

        Args:
            buy_order: The BUY order being filled.
            fill_amount: Amount filled in this fill event.
            fill_price: Execution price for this fill event.
            opened_at: Datetime when the fill occurred.

        Returns:
            Trade: The newly created trade, or ``None`` if the fill
            amount is non-positive or the order is in a terminal
            non-fillable state.
        """
        if buy_order.status in (
            OrderStatus.CANCELED.value,
            OrderStatus.EXPIRED.value,
            OrderStatus.REJECTED.value,
        ):
            return None

        if fill_amount is None or fill_amount <= 0:
            return None

        data = {
            "buy_order": buy_order,
            "target_symbol": buy_order.target_symbol,
            "trading_symbol": buy_order.trading_symbol,
            "amount": fill_amount,
            "available_amount": fill_amount,
            "filled_amount": fill_amount,
            "remaining": 0,
            "opened_at": opened_at,
            "cost": fill_amount * fill_price,
            "status": TradeStatus.OPEN.value,
        }
        strategy_id = getattr(buy_order, "strategy_id", None) or \
            (buy_order.metadata or {}).get("strategy_id")
        if strategy_id is not None:
            data["strategy_id"] = strategy_id
            data["metadata"] = {"strategy_id": strategy_id}

        trade = self.create(data)

        # The SQL Trade constructor pulls ``open_price`` from
        # ``buy_order.price``; force it to the fill price for this
        # specific fill so partial fills at different prices remain
        # accurate.
        if trade.open_price != fill_price:
            trade = self.update(trade.id, {"open_price": fill_price})

        # Materialize any pending stop-loss / take-profit rules queued
        # on the buy order onto this freshly created trade.
        for spec in buy_order.pending_stop_losses:
            self.add_stop_loss(
                trade,
                percentage=spec["percentage"],
                trailing=spec.get("trailing", False),
                sell_percentage=spec.get("sell_percentage", 100),
                created_at=opened_at,
                mirror_on_exchange=spec.get("mirror_on_exchange", False),
            )

        for spec in buy_order.pending_take_profits:
            self.add_take_profit(
                trade,
                percentage=spec["percentage"],
                trailing=spec.get("trailing", False),
                sell_percentage=spec.get("sell_percentage", 100),
                created_at=opened_at,
                mirror_on_exchange=spec.get("mirror_on_exchange", False),
            )

        self._dispatch_trade_hook("on_trade_created", trade)
        self._dispatch_trade_hook("on_trade_opened", trade)
        return trade

    # ------------------------------------------------------------------
    # #434 phase 2 — SHORT / COVER trade lifecycle.
    #
    # Mirrors the v9.0 long-side flow:
    #   - ``create_short_trade_at_fill`` is the SHORT analog of
    #     ``create_trade_at_fill``; it opens a Trade with ``is_short``
    #     set so per-bar reprice and net_gain math invert correctly.
    #   - ``close_short_trade_with_filled_cover_order`` is the COVER
    #     analog of ``update_trade_with_filled_sell_order`` but takes
    #     the simpler direct-update path (no TradeAllocation rows in
    #     phase 2; stop-loss / take-profit on shorts arrives in a
    #     later phase).
    # ------------------------------------------------------------------

    def create_short_trade_at_fill(
        self, short_order, fill_amount, fill_price, opened_at
    ) -> Union[Trade, None]:
        """Create a SHORT trade for a single fill event on a short
        order. Mirrors :py:meth:`create_trade_at_fill` but flips the
        direction and tags the trade with ``is_short=True``.
        """
        if short_order.status in (
            OrderStatus.CANCELED.value,
            OrderStatus.EXPIRED.value,
            OrderStatus.REJECTED.value,
        ):
            return None

        if fill_amount is None or fill_amount <= 0:
            return None

        # Cost for a short trade is the proceeds at entry (notional).
        # This mirrors the vector engine (#433) so net_gain math stays
        # symmetric across engines.
        cost = fill_amount * fill_price
        data = {
            "buy_order": short_order,
            "target_symbol": short_order.target_symbol,
            "trading_symbol": short_order.trading_symbol,
            "amount": fill_amount,
            "available_amount": fill_amount,
            "filled_amount": fill_amount,
            "remaining": 0,
            "opened_at": opened_at,
            "cost": cost,
            "status": TradeStatus.OPEN.value,
            "is_short": True,
        }
        strategy_id = getattr(short_order, "strategy_id", None) or \
            (short_order.metadata or {}).get("strategy_id")
        if strategy_id is not None:
            data["strategy_id"] = strategy_id
            data["metadata"] = {"strategy_id": strategy_id}

        trade = self.create(data)

        # The SQL Trade constructor pulls ``open_price`` from
        # ``short_order.price``; force it to the fill price for this
        # specific fill so partial fills at different prices remain
        # accurate.
        if trade.open_price != fill_price:
            trade = self.update(trade.id, {"open_price": fill_price})

        # #434 phase 3 — materialize any pending stop-loss /
        # take-profit rules queued on the short order onto this new
        # short trade. ``add_stop_loss`` / ``add_take_profit`` copy
        # ``trade.is_short`` into the created SL/TP so the trigger
        # math inverts correctly.
        for spec in getattr(short_order, "pending_stop_losses", []) or []:
            self.add_stop_loss(
                trade,
                percentage=spec["percentage"],
                trailing=spec.get("trailing", False),
                sell_percentage=spec.get("sell_percentage", 100),
                created_at=opened_at,
                mirror_on_exchange=spec.get("mirror_on_exchange", False),
            )

        for spec in getattr(short_order, "pending_take_profits", []) or []:
            self.add_take_profit(
                trade,
                percentage=spec["percentage"],
                trailing=spec.get("trailing", False),
                sell_percentage=spec.get("sell_percentage", 100),
                created_at=opened_at,
                mirror_on_exchange=spec.get("mirror_on_exchange", False),
            )

        self._dispatch_trade_hook("on_trade_created", trade)
        self._dispatch_trade_hook("on_trade_opened", trade)
        return trade

    def close_short_trade_with_filled_cover_order(
        self, filled_difference, cover_order
    ):
        """Close (or partially close) one or more open SHORT trades on
        the target symbol with the filled portion of a COVER order.

        Uses FIFO across open short trades for the symbol/portfolio.
        Realizes ``net_gain = (open_price - fill_price) * portion`` per
        trade — inverse of the long path — and closes the trade when
        ``available_amount`` reaches zero. Skips ``TradeAllocation``
        bookkeeping in phase 2 (stop-loss / take-profit on shorts is
        a later phase).
        """
        if filled_difference is None or filled_difference <= 0:
            return

        position = self.position_repository.get(cover_order.position_id)
        # #434 phase 3 — honour an explicit trade allocation stashed
        # by the order service (e.g. from a SL/TP-triggered COVER).
        # The hint is a list of ``{"trade_id": int, "amount": float}``
        # dicts. When present, allocate to those trades first
        # (preserving order); fall through to FIFO if it doesn't
        # absorb the entire fill.
        explicit_allocations = (cover_order.metadata or {}).get(
            "_cover_trade_allocations"
        )
        # Find all open short trades for this position's symbol
        # belonging to the same portfolio.
        candidate_trades = self.get_all(
            {
                "target_symbol": cover_order.target_symbol,
                "trading_symbol": cover_order.trading_symbol,
                "portfolio_id": position.portfolio_id,
                "status": TradeStatus.OPEN.value,
            }
        )
        short_trades = [t for t in candidate_trades if t.is_short]
        # FIFO: oldest opened first.
        short_trades.sort(key=lambda t: t.opened_at)

        if explicit_allocations:
            # Stable reorder: requested trade_ids first (preserving the
            # caller-supplied order), all others (FIFO) appended.
            requested_ids = [
                a["trade_id"] for a in explicit_allocations
                if a.get("trade_id") is not None
            ]
            by_id = {t.id: t for t in short_trades}
            head = [by_id[i] for i in requested_ids if i in by_id]
            tail = [t for t in short_trades if t.id not in set(requested_ids)]
            short_trades = head + tail

        remaining = filled_difference
        fill_price = cover_order.get_price()
        closed_at = cover_order.updated_at or cover_order.created_at
        # Re-fetch a local handle so attaching it to the trade's
        # session in ``add_order_to_trade`` does not detach the
        # caller's reference (which the order_service.update flow
        # still needs to read ``status`` from).
        cover_order_id = cover_order.get_id()

        for trade in short_trades:
            if remaining <= 0:
                break

            available = trade.available_amount or 0
            if available <= 0:
                continue

            portion = min(available, remaining)
            # Inverse of the long path: short gains when fill < open.
            net_gain_contribution = (
                trade.open_price - fill_price
            ) * portion

            new_available = available - portion
            new_net_gain = (trade.net_gain or 0) + net_gain_contribution

            updates = {
                "available_amount": new_available,
                "net_gain": new_net_gain,
                "updated_at": closed_at,
            }
            if new_available <= 0:
                updates["status"] = TradeStatus.CLOSED.value
                updates["closed_at"] = closed_at

            self.update(trade.id, updates)
            if self.trade_hook_dispatcher is not None:
                updated_trade = self.get(trade.id)
                if updates.get("status") == TradeStatus.CLOSED.value:
                    self._dispatch_trade_hook(
                        "on_trade_closed", updated_trade
                    )
                else:
                    self._dispatch_trade_hook(
                        "on_trade_updated", updated_trade
                    )
            local_cover_order = self.order_repository.get(cover_order_id)
            self.repository.add_order_to_trade(trade, local_cover_order)

            remaining -= portion

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
        # v9.0 (#431) — STOP SELL orders carry no ``price`` until they
        # trigger and fill. Fall back to ``stop_price`` for the initial
        # allocation accounting so reservation succeeds; the eventual
        # fill-time sync will overwrite trade state with the real
        # execution price.
        if sell_price is None or sell_price == 0:
            sell_price = sell_order.stop_price or 0
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
        if self.trade_hook_dispatcher is not None:
            updated_trade = self.get(trade_id)
            if update_data.get("status") == TradeStatus.CLOSED.value:
                self._dispatch_trade_hook("on_trade_closed", updated_trade)
            else:
                self._dispatch_trade_hook("on_trade_updated", updated_trade)
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
            if not trade.is_short and trade.available_amount > 0:
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
                    prev_price = stop_loss.stop_loss_price
                    stop_loss.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_stop_losses.append(stop_loss)

                    if (
                        self.trade_hook_dispatcher is not None
                        and stop_loss.stop_loss_price != prev_price
                    ):
                        hook_name = (
                            "on_trade_trailing_stop_loss_updated"
                            if stop_loss.trailing
                            else "on_trade_stop_loss_updated"
                        )
                        self._dispatch_trade_hook(hook_name, trade)

            for take_profit in take_profits:

                if take_profit.active:
                    prev_price = take_profit.take_profit_price
                    take_profit.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_take_profits.append(take_profit)

                    if (
                        self.trade_hook_dispatcher is not None
                        and take_profit.take_profit_price != prev_price
                    ):
                        self._dispatch_trade_hook(
                            "on_trade_take_profit_updated", trade
                        )

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
            trade = self.get(trade_data["trade_id"])
            if trade.is_short:
                raise OperationalException(
                    "SELL orders can only close long trades"
                )
            self._allocate_sell_to_trade(
                trade_data["trade_id"], sell_order, trade_data["amount"]
            )

    def create_trade_allocations(
        self, sell_order, trades=None, stop_losses=None, take_profits=None,
        position_mode=PositionMode.NETTING,
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
        # v9.0 (#431) — STOP SELL orders carry no ``price`` until they
        # trigger and fill. Fall back to ``stop_price`` so portfolio
        # revenue/cost accounting succeeds; the eventual fill-time
        # sync will replace these estimates with real values.
        if sell_price is None or sell_price == 0:
            sell_price = sell_order.stop_price or 0
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

        if PositionMode(position_mode) == PositionMode.HEDGE:
            self.position_repository.update(
                position.id, {"long_cost": position.long_cost - cost}
            )
        else:
            position.cost -= cost
            self.position_repository.save(position)

        # Update the net gain, net size of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain += net_gain
        portfolio.net_size += net_gain
        portfolio.total_revenue += sell_price * sell_amount
        self.portfolio_repository.save(portfolio)

    def update_trade_with_removed_sell_order(
        self, sell_order, position_mode=PositionMode.NETTING
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
        if PositionMode(position_mode) == PositionMode.HEDGE:
            self.position_repository.update(
                position.id, {"long_cost": position.long_cost + position_cost}
            )
        else:
            position.cost += position_cost
            self.position_repository.save(position)

        # Update the net gain of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain -= total_net_gain
        portfolio.net_size -= total_net_gain
        self.portfolio_repository.save(portfolio)
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
        trade=None,
        percentage: float = None,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: datetime = None,
        order=None,
        mirror_on_exchange: bool = False,
    ) -> TradeStopLoss:
        """
        Function to add a stop loss to a trade or a pending buy order.

        v9.0 (#431) — when ``order`` is supplied, the stop-loss spec
        is queued on the buy order via
        :meth:`Order.add_pending_stop_loss` and is materialized onto
        each trade created when the order fills. This is the only way
        to attach risk rules to a BUY order that has not yet filled,
        because trades are no longer created eagerly at BUY creation.

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
            trade: Trade object representing the trade. Mutually
                exclusive with ``order``.
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trailing (bool): representing whether the stop loss is a
                trailing stop loss or not. Default is False.
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered.
            created_at: datetime representing the creation date of the
                stop loss. If None, the current datetime will be used.
            order: Order object representing a BUY order. When
                supplied, the spec is queued on the order and applied
                to each trade materialized at fill time.

        Returns:
            None
        """
        if order is not None and trade is not None:
            raise OperationalException(
                "add_stop_loss accepts either ``trade`` or ``order``, "
                "not both."
            )

        if order is not None:
            prev_updated_at = order.updated_at
            order.add_pending_stop_loss(
                percentage=percentage,
                trailing=trailing,
                sell_percentage=sell_percentage,
                mirror_on_exchange=mirror_on_exchange,
            )
            # Keep persisted JSON column in sync with the in-memory
            # metadata dict — SQLAlchemy doesn't detect in-place dict
            # mutations on the metadata attribute.
            if hasattr(order, "metadata_json"):
                import json as _json
                order.metadata_json = _json.dumps(order.metadata)
            # Preserve updated_at so backtest fill checks (which
            # filter OHLCV by Datetime >= updated_at) still match
            # historical bars after a metadata-only save (#434).
            order.updated_at = prev_updated_at
            try:
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(order, "updated_at")
            except Exception:
                pass
            self.order_repository.save(order)
            return None

        if trade is None:
            raise OperationalException(
                "add_stop_loss requires either ``trade`` or ``order``."
            )

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
            "is_short": bool(getattr(trade, "is_short", False)),
            "mirror_on_exchange": mirror_on_exchange,
            "created_at": created_at if created_at is not None
            else datetime.now(tz=timezone.utc)
        }
        created = self.trade_stop_loss_repository.create(creation_data)
        self._dispatch_trade_hook("on_trade_stop_loss_created", trade)
        if trailing:
            self._dispatch_trade_hook(
                "on_trade_trailing_stop_loss_created", trade
            )
        return created

    def add_take_profit(
        self,
        trade=None,
        percentage: float = None,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: datetime = None,
        order=None,
        mirror_on_exchange: bool = False,
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
        if order is not None and trade is not None:
            raise OperationalException(
                "add_take_profit accepts either ``trade`` or ``order``, "
                "not both."
            )

        if order is not None:
            prev_updated_at = order.updated_at
            order.add_pending_take_profit(
                percentage=percentage,
                trailing=trailing,
                sell_percentage=sell_percentage,
                mirror_on_exchange=mirror_on_exchange,
            )
            if hasattr(order, "metadata_json"):
                import json as _json
                order.metadata_json = _json.dumps(order.metadata)
            order.updated_at = prev_updated_at
            try:
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(order, "updated_at")
            except Exception:
                pass
            self.order_repository.save(order)
            return None

        if trade is None:
            raise OperationalException(
                "add_take_profit requires either ``trade`` or ``order``."
            )

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
            "is_short": bool(getattr(trade, "is_short", False)),
            "mirror_on_exchange": mirror_on_exchange,
            "created_at": created_at if created_at is not None
            else datetime.now(tz=timezone.utc)
        }
        created = self.trade_take_profit_repository.create(creation_data)
        self._dispatch_trade_hook("on_trade_take_profit_created", trade)
        return created

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
            # #434 phase 3 — short trades close with COVER, longs
            # with SELL.
            close_side = OrderSide.COVER.value if trade.is_short \
                else OrderSide.SELL.value
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": close_side,
                    "portfolio_id": portfolio_id,
                    "metadata": {"order_reason": "stop_loss"},
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
            close_side = OrderSide.COVER.value if trade.is_short \
                else OrderSide.SELL.value
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": close_side,
                    "portfolio_id": portfolio_id,
                    "metadata": {"order_reason": "take_profit"},
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
