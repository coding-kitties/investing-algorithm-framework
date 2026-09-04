from abc import ABC, abstractmethod
from typing import List, Dict
import polars as pl
from investing_algorithm_framework.domain import Trade, Order, \
    INDEX_DATETIME, OrderSide, OrderStatus, OrderType, TradingCost


class TradeOrderEvaluator(ABC):

    def __init__(
        self,
        trade_service,
        trade_stop_loss_service,
        trade_take_profit_service,
        order_service,
        configuration_service=None,
        blotter=None,
        context=None,
        trading_costs=None,
        portfolio_configuration=None,
    ):
        self.trade_service = trade_service
        self.trade_stop_loss_service = trade_stop_loss_service
        self.trade_take_profit_service = trade_take_profit_service
        self.order_service = order_service
        self.configuration_service = configuration_service
        self._blotter = blotter
        self._context = context
        self._trading_costs = trading_costs or []
        self._portfolio_configuration = portfolio_configuration

    @abstractmethod
    def evaluate(
        self,
        open_trades: List[Trade],
        open_orders: List[Order],
        ohlcv_data: Dict[str, pl.DataFrame]
    ):
        """
        Evaluate trades and orders based on OHLCV data. This
        function is responsible for updating open orders and open trades.
        The evaluation process includes checking if orders have been executed
        and updating the trades with the latest prices and execution status.
        Additionally, it may trigger stop-loss and take-profit orders
        based on the current market conditions.

        Args:
            open_trades (List[Trade]): List of open Trade objects.
            open_orders (List[Order]): List of open Order objects.
            ohlcv_data (dict[str, pl.DataFrame]): Mapping of
                symbol -> OHLCV Polars DataFrame.

        Returns:
            List[dict]: Updated trades with latest prices and execution status.
        """
        pass

    def _create_order(self, order_data):
        """
        Create an order through the blotter if available,
        otherwise fall back to the order service directly.
        """
        if self._blotter is not None and self._context is not None:
            return self._blotter.place_order(order_data, self._context)
        return self.order_service.create(order_data)

    def _check_take_profits(self):
        current_date = self.configuration_service.config[INDEX_DATETIME]
        take_profits_orders_data = self.trade_service \
            .get_triggered_take_profit_orders()

        for take_profit_order in take_profits_orders_data:
            take_profits = take_profit_order["take_profits"]
            # `_create_order` deletes "trades"/"stop_losses"/
            # "take_profits" from this dict in place (OrderService.
            # create), so capture the trade refs before calling it.
            trades = take_profit_order.get("trades", [])
            for trade_ref in trades:
                self.order_service.cancel_mirror_orders_for_trade(
                    trade_ref["trade_id"]
                )
            self._create_order(take_profit_order)
            self.trade_take_profit_service.mark_triggered(
                [
                    take_profit.get("take_profit_id")
                    for take_profit in take_profits
                ],
                trigger_date=current_date
            )
            self._dispatch_hook_for_trades(
                trades, "on_trade_take_profit_triggered"
            )

    def _check_stop_losses(self):
        current_date = self.configuration_service.config[INDEX_DATETIME]
        stop_losses_orders_data = self.trade_service \
            .get_triggered_stop_loss_orders()

        for stop_loss_order in stop_losses_orders_data:
            stop_losses = stop_loss_order["stop_losses"]
            # See note in _check_take_profits: capture before mutation.
            trades = stop_loss_order.get("trades", [])

            for trade_ref in trades:
                self.order_service.cancel_mirror_orders_for_trade(
                    trade_ref["trade_id"]
                )

            self._create_order(stop_loss_order)
            self.trade_stop_loss_service.mark_triggered(
                [
                    stop_loss.get("stop_loss_id") for stop_loss in
                    stop_losses
                ],
                trigger_date=current_date
            )
            dispatcher = getattr(
                self.trade_service, "trade_hook_dispatcher", None
            )
            if dispatcher is None:
                continue
            trailing = any(
                getattr(
                    self.trade_stop_loss_service.get(
                        stop_loss.get("stop_loss_id")
                    ),
                    "trailing",
                    False,
                )
                for stop_loss in stop_losses
            )
            hook_name = (
                "on_trade_trailing_stop_loss_triggered" if trailing
                else "on_trade_stop_loss_triggered"
            )
            self._dispatch_hook_for_trades(trades, hook_name)

    def _dispatch_hook_for_trades(self, trades, hook_name):
        """
        Notify the owning strategy for each trade dict (each with a
        "trade_id" key) referenced by a triggered stop-loss/take-profit
        order. No-op if no hooks are active for any strategy.
        """
        dispatcher = getattr(self.trade_service, "trade_hook_dispatcher", None)
        if dispatcher is None:
            return

        for trade_ref in trades:
            trade = self.trade_service.get(trade_ref["trade_id"])
            dispatcher.dispatch(hook_name, trade)

    def _resolve_trading_cost(self, symbol, order=None):
        """Resolve TradingCost for a given symbol.

        ``order`` is accepted (but unused here) so subclasses can
        override with order-aware resolution (e.g.
        ``DefaultTradeOrderEvaluator`` falling back to a real exchange
        fee estimate for paper-traded orders).
        """
        # Extract target symbol (before the /)
        target = symbol.split("/")[0] if "/" in symbol else symbol
        return TradingCost.resolve(
            target, self._trading_costs, self._portfolio_configuration
        )

    def _check_has_executed(self, order, ohlcv_df):
        """
        Check if the order has been executed based on OHLCV data.

        When a blotter is available (via the parent TradeOrderEvaluator),
        fill pricing, commission, and fill amounts are delegated to the
        blotter's models. Otherwise, TradingCost is used as a fallback.

        BUY ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the lowest low price of the series is below or equal
            to the order price, the order is filled.

        SELL ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the highest high price of the series is above or equal
            to the order price, the order is filled.

        Args:
            order (Order): Order.
            ohlcv_df (pl.DataFrame): OHLCV DataFrame for the symbol.

        Returns:
            None
        """

        if ohlcv_df.is_empty():
            return

        # Extract attributes from the order object
        updated_at = order.updated_at
        order_side = order.order_side
        order_price = order.price
        ohlcv_data_after_order = ohlcv_df.filter(
            pl.col('Datetime') >= updated_at
        )

        if ohlcv_data_after_order.is_empty():
            return

        # Market orders: fill at the open of the first available candle
        if OrderType.MARKET.equals(order.order_type):
            first_candle = ohlcv_data_after_order.head(1)
            base_price = first_candle["Open"][0]
            volume = (
                first_candle["Volume"][0]
                if "Volume" in first_candle.columns
                else None
            )
            self._apply_fill(
                order, base_price, order_side, volume,
                is_market_order=True
            )
            return

        # Stop / Stop-Limit orders: first check whether the trigger
        # condition is met. Once triggered, a STOP becomes a market
        # order (fill at trigger price) and a STOP_LIMIT becomes a
        # limit order at the configured limit price.
        is_stop = OrderType.STOP.equals(order.order_type)
        is_stop_limit = OrderType.STOP_LIMIT.equals(order.order_type)

        if (is_stop or is_stop_limit) and not order.is_triggered():
            stop_price = order.get_stop_price()

            if stop_price is None:
                return

            # SELL stop triggers when price drops to or below stop_price;
            # BUY stop triggers when price rises to or above stop_price.
            if OrderSide.SELL.equals(order_side) \
                    or OrderSide.SHORT.equals(order_side):
                trigger_candles = ohlcv_data_after_order.filter(
                    pl.col('Low') <= stop_price
                )
            elif OrderSide.BUY.equals(order_side) \
                    or OrderSide.COVER.equals(order_side):
                trigger_candles = ohlcv_data_after_order.filter(
                    pl.col('High') >= stop_price
                )
            else:
                return

            if trigger_candles.is_empty():
                return

            triggered_candle = trigger_candles.head(1)
            order.set_triggered_at(triggered_candle["Datetime"][0])

            # v9.0 (#431) — persist the trigger timestamp immediately
            # so that a STOP_LIMIT that triggers but doesn't fill in
            # the same bar still remembers it triggered when the
            # evaluator reloads the order in a later iteration.
            self.order_service.repository.update(
                order.id,
                {"triggered_at": order.get_triggered_at()},
            )

            if is_stop:
                # STOP becomes a market order — fill at the stop price
                # using the triggering candle's volume.
                volume = (
                    triggered_candle["Volume"][0]
                    if "Volume" in triggered_candle.columns
                    else None
                )
                self._apply_fill(
                    order, stop_price, order_side, volume,
                    is_market_order=True
                )
                return

            # STOP_LIMIT: continue and fall through to limit-fill logic
            # using the configured limit price (`order.price`). Restrict
            # the fill search to candles at or after the trigger.
            ohlcv_data_after_order = ohlcv_data_after_order.filter(
                pl.col('Datetime') >= order.get_triggered_at()
            )

            if ohlcv_data_after_order.is_empty():
                return

        # Limit orders (including triggered STOP_LIMIT):
        # check if OHLCV data triggers a fill.
        # BUY / COVER fill when Low <= limit (a seller meets our bid).
        # SELL / SHORT fill when High >= limit (a buyer meets our ask).
        if OrderSide.BUY.equals(order_side) \
                or OrderSide.COVER.equals(order_side):
            fill_candles = ohlcv_data_after_order.filter(
                pl.col('Low') <= order_price
            )
        elif OrderSide.SELL.equals(order_side) \
                or OrderSide.SHORT.equals(order_side):
            fill_candles = ohlcv_data_after_order.filter(
                pl.col('High') >= order_price
            )
        else:
            return

        if fill_candles.is_empty():
            return

        first_fill = fill_candles.head(1)
        volume = (
            first_fill["Volume"][0]
            if "Volume" in first_fill.columns
            else None
        )
        self._apply_fill(
            order, order_price, order_side, volume,
            is_market_order=False
        )

    def _apply_fill(
        self, order, base_price, order_side, volume,
        is_market_order=False
    ):
        """
        Apply a fill to an order, using blotter methods when available
        or falling back to TradingCost.

        Supports partial fills when the blotter's fill model limits
        the fillable amount (e.g. VolumeBasedFill).
        """
        remaining = (
            order.remaining
            if order.remaining is not None
            else order.amount
        )

        if self._blotter is not None:
            fill_price = self._blotter.get_fill_price(
                base_price, order_side, remaining, volume
            )
            fill_amount = min(
                self._blotter.get_fill_amount(remaining, volume),
                remaining
            )
            if OrderSide.BUY.equals(order_side) \
                    or OrderSide.COVER.equals(order_side):
                slippage = fill_price - base_price
            else:
                slippage = base_price - fill_price
            fee = self._blotter.on_fill(
                order.id, order.symbol, order_side,
                fill_price, base_price, fill_amount,
            )
            fee_rate = self._blotter.get_commission_rate()
        else:
            tc = self._resolve_trading_cost(order.symbol, order=order)
            fill_amount = min(
                tc.get_max_fill_amount(remaining, volume), remaining,
            )
            if OrderSide.BUY.equals(order_side) \
                    or OrderSide.COVER.equals(order_side):
                fill_price = tc.get_buy_fill_price(
                    base_price, amount=fill_amount, volume=volume,
                )
                slippage = fill_price - base_price
            else:
                fill_price = tc.get_sell_fill_price(
                    base_price, amount=fill_amount, volume=volume,
                )
                slippage = base_price - fill_price
            fee = tc.get_fee(fill_price * fill_amount)
            fee_rate = (
                tc.fee_percentage / 100 if tc.fee_percentage else None
            )

        if fill_amount <= 0:
            return

        new_filled = (order.filled or 0) + fill_amount
        new_remaining = order.amount - new_filled
        accumulated_fee = (order.order_fee or 0) + fee

        if new_remaining <= 0:
            # Full fill
            update_data = {
                'status': OrderStatus.CLOSED.value,
                'remaining': 0,
                'filled': order.amount,
                'price': fill_price,
                'order_fee': accumulated_fee,
                'slippage': slippage,
            }
            if fee_rate is not None:
                update_data['order_fee_rate'] = fee_rate
        else:
            # Partial fill — order stays open for next evaluation
            update_data = {
                'filled': new_filled,
                'remaining': new_remaining,
                'order_fee': accumulated_fee,
            }

        # Persist trigger timestamp for stop / stop-limit orders so
        # subsequent evaluations don't re-trigger.
        if order.is_triggered():
            update_data['triggered_at'] = order.get_triggered_at()

        # v9.0 (#431) — the market-order portfolio reconciliation that
        # used to live here has been removed. Slippage between the
        # reservation price (captured at order-creation time) and the
        # actual fill price is now settled uniformly inside
        # ``OrderService._sync_with_buy_order_filled`` for LIMIT,
        # MARKET, STOP and STOP_LIMIT orders.

        self.order_service.update(order.id, update_data)
