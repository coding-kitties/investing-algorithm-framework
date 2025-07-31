from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import Trade, Order
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
        open_trades: List[Trade],
        open_orders: List[Order],
        ohlcv_data: Dict[str, pl.DataFrame]
    ):
        """
        Evaluate trades and orders based on OHLCV data.

        Args:
            open_orders (List[Order]): List of open Order objects.
            open_trades (List[Trade]): List of open Trade objects.
            ohlcv_data (dict[str, pl.DataFrame]): Mapping of
                symbol -> OHLCV Polars DataFrame.

        Returns:
            List[dict]: Updated trades with latest prices and execution status.
        """
        self.order_service.check_pending_orders()

        if len(open_trades) > 0:
            for open_trade in open_trades:
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

            self.trade_service.save_all(open_trades)

            stop_losses_orders_data = self.trade_service \
                .get_triggered_stop_loss_orders()

            for stop_loss_order in stop_losses_orders_data:
                self.order_service.create(stop_loss_order)

            take_profits_orders_data = self.trade_service \
                .get_triggered_take_profit_orders()

            for take_profit_order in take_profits_orders_data:
                self.order_service.create(take_profit_order)
