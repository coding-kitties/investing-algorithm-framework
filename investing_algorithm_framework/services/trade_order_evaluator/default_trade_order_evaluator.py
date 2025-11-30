from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import Trade, Order, INDEX_DATETIME
from .trade_order_evaluator import TradeOrderEvaluator


class DefaultTradeOrderEvaluator(TradeOrderEvaluator):

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
        current_date = self.configuration_service.config[INDEX_DATETIME]

        if len(open_trades) > 0:
            for open_trade in open_trades:
                data = ohlcv_data[open_trade.symbol]

                if data is None or data.is_empty():
                    continue

                # Get last row of data
                last_row = data.tail(1)
                last_row_date = last_row["Datetime"][0]
                update_data = {
                    "last_reported_price": last_row["Close"][0],
                    "last_reported_price_datetime": last_row_date,
                    "updated_at": current_date
                }
                open_trade.update(update_data)

            self.trade_service.save_all(open_trades)
            self._check_take_profits()
            self._check_stop_losses()
