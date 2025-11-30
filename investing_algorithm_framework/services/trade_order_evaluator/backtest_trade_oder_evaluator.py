from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    Trade, Order
from .trade_order_evaluator import TradeOrderEvaluator


class BacktestTradeOrderEvaluator(TradeOrderEvaluator):

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
        # First check pending orders
        for open_order in open_orders:
            data = ohlcv_data.get(open_order.symbol)
            self._check_has_executed(open_order, data)

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
            self._check_take_profits()
            self._check_stop_losses()

    def _check_has_executed(self, order, ohlcv_df):
        """
        Check if the order has been executed based on OHLCV data.

        BUY ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the lowest low price of the series is below or equal
            to the order price, e.g. if you buy asset at price 100
            and the low price of the series is 99, then the order is filled.

        SELL ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the highest high price of the series is above or equal
            to the order price, e.g. if you sell asset at price 100
            and the high price of the series is 101, then the order is filled.

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

        if OrderSide.BUY.equals(order_side):
            # Check if the low price drops below or equals the order price
            if (ohlcv_data_after_order['Low'] <= order_price).any():
                self.order_service.update(
                    order.id, {
                        'status': OrderStatus.CLOSED.value,
                        'remaining': 0,
                        'filled': order.amount
                    }
                )

        elif OrderSide.SELL.equals(order_side):
            # Check if the high price goes above or equals the order price
            if (ohlcv_data_after_order['High'] >= order_price).any():
                self.order_service.update(
                    order.id, {
                        'status': OrderStatus.CLOSED.value,
                        'remaining': 0,
                        'filled': order.amount
                    }
                )
