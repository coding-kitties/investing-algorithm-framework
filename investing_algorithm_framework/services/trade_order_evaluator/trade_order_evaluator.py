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
        configuration_service=None
    ):
        self.trade_service = trade_service
        self.trade_stop_loss_service = trade_stop_loss_service
        self.trade_take_profit_service = trade_take_profit_service
        self.order_service = order_service
        self.configuration_service = configuration_service

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

    def _check_take_profits(self):
        current_date = self.configuration_service.config[INDEX_DATETIME]
        take_profits_orders_data = self.trade_service \
            .get_triggered_take_profit_orders()

        for take_profit_order in take_profits_orders_data:
            take_profits = take_profit_order["take_profits"]
            self.order_service.create(take_profit_order)
            self.trade_take_profit_service.mark_triggered(
                [
                    take_profit.get("take_profit_id")
                    for take_profit in take_profits
                ],
                trigger_date=current_date
            )

    def _check_stop_losses(self):
        current_date = self.configuration_service.config[INDEX_DATETIME]
        stop_losses_orders_data = self.trade_service \
            .get_triggered_stop_loss_orders()

        for stop_loss_order in stop_losses_orders_data:
            stop_losses = stop_loss_order["stop_losses"]

            self.order_service.create(stop_loss_order)
            self.trade_stop_loss_service.mark_triggered(
                [
                    stop_loss.get("stop_loss_id") for stop_loss in
                    stop_losses
                ],
                trigger_date=current_date
            )
