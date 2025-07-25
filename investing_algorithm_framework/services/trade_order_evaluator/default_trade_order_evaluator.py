from typing import List

import polars as pl

from .trade_order_evaluator import TradeOrderEvaluator


class DefaultTradeOrderEvaluator(TradeOrderEvaluator):

    def __init__(
        self,
        trade_service,
        order_service
    ):
        super().__init__(trade_service, order_service)

    def evaluate(
        self,
        trades: List[dict],
        orders: List[dict],
        ohlcv_data: dict[str, pl.DataFrame]
    ) -> List[dict]:
        """
        Evaluate trades and orders based on OHLCV data.

        Args:
            trades (List[dict]): List of trade dictionaries.
            orders (List[dict]): List of order dictionaries.
            ohlcv_data (dict[str, pl.DataFrame]): Mapping of
                symbol -> OHLCV Polars DataFrame.

        Returns:
            List[dict]: Updated trades with latest prices and execution status.
        """
        print("checking pending orders")

        self.order_service.check_pending_orders()

        for open_trade in trades:
            data = ohlcv_data[open_trade.symbol]

            if data is None or data.is_empty():
                continue

            # Get last row of data
            last_row = data.tail(1)
            update_data = {
                "last_reported_price": last_row["Close"][0],
                "last_reported_price_datetime": last_row["Datetime"][0],
                "updated_at": last_row["Datetime"][0]
            }
            open_trade.update(update_data)

        self.trade_service.save_all(trades)

        stop_losses_orders_data = self.trade_service \
            .get_triggered_stop_loss_orders()

        for stop_loss_order in stop_losses_orders_data:
            self.order_service.create(stop_loss_order)

        take_profits_orders_data = self.trade_service \
            .get_triggered_take_profit_orders()

        for take_profit_order in take_profits_orders_data:
            self.order_service.create(take_profit_order)
