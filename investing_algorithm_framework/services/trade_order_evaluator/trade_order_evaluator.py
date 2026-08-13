from abc import ABC, abstractmethod
from typing import List, Dict
import polars as pl
from investing_algorithm_framework.domain import Trade, Order, INDEX_DATETIME


class TradeOrderEvaluator(ABC):

    def __init__(
        self,
        trade_service,
        trade_stop_loss_service,
        trade_take_profit_service,
        order_service,
        configuration_service=None,
        blotter=None,
        context=None
    ):
        self.trade_service = trade_service
        self.trade_stop_loss_service = trade_stop_loss_service
        self.trade_take_profit_service = trade_take_profit_service
        self.order_service = order_service
        self.configuration_service = configuration_service
        self._blotter = blotter
        self._context = context

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
