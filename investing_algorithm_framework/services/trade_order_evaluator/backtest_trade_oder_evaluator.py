from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    Trade, Order, TradeStatus, TradingCost
from .trade_order_evaluator import TradeOrderEvaluator


class BacktestTradeOrderEvaluator(TradeOrderEvaluator):

    def __init__(self, *args, trading_costs=None,
                 portfolio_configuration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._trading_costs = trading_costs or []
        self._portfolio_configuration = portfolio_configuration

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

            if data is None or data.is_empty():
                continue

            self._check_has_executed(open_order, data)

        # Re-query open trades to include newly created trades
        # from filled orders above (#384)
        open_trades = self.trade_service.get_all(
            {"status": TradeStatus.OPEN.value}
        )

        if len(open_trades) > 0:
            for open_trade in open_trades:
                data = ohlcv_data.get(open_trade.symbol)

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

    def _resolve_trading_cost(self, symbol):
        """Resolve TradingCost for a given symbol."""
        # Extract target symbol (before the /)
        target = symbol.split("/")[0] if "/" in symbol else symbol
        return TradingCost.resolve(
            target, self._trading_costs, self._portfolio_configuration
        )

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

        tc = self._resolve_trading_cost(order.symbol)

        if OrderSide.BUY.equals(order_side):
            # Check if the low price drops below or equals the order price
            if (ohlcv_data_after_order['Low'] <= order_price).any():
                fill_price = tc.get_buy_fill_price(order_price)
                fee = tc.get_fee(fill_price * order.amount)
                slippage = fill_price - order_price
                update_data = {
                    'status': OrderStatus.CLOSED.value,
                    'remaining': 0,
                    'filled': order.amount,
                    'price': fill_price,
                    'order_fee': fee,
                    'slippage': slippage,
                }
                if tc.fee_percentage:
                    update_data['order_fee_rate'] = \
                        tc.fee_percentage / 100
                self.order_service.update(order.id, update_data)

        elif OrderSide.SELL.equals(order_side):
            # Check if the high price goes above or equals the order price
            if (ohlcv_data_after_order['High'] >= order_price).any():
                fill_price = tc.get_sell_fill_price(order_price)
                fee = tc.get_fee(fill_price * order.amount)
                slippage = order_price - fill_price
                update_data = {
                    'status': OrderStatus.CLOSED.value,
                    'remaining': 0,
                    'filled': order.amount,
                    'price': fill_price,
                    'order_fee': fee,
                    'slippage': slippage,
                }
                if tc.fee_percentage:
                    update_data['order_fee_rate'] = \
                        tc.fee_percentage / 100
                self.order_service.update(order.id, update_data)
