from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import Trade, Order, TradeStatus
from .trade_order_evaluator import TradeOrderEvaluator


class BacktestTradeOrderEvaluator(TradeOrderEvaluator):
    """
    Event-backtest trade/order evaluator.

    ``_resolve_trading_cost``, ``_check_has_executed``, and
    ``_apply_fill`` (the OHLCV-driven fill simulation) live on the
    shared ``TradeOrderEvaluator`` base class so
    ``DefaultTradeOrderEvaluator`` can reuse the exact same logic to
    validate local paper-trading fills.
    """

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
                # Route through TradeService.update() (not a direct
                # domain-object mutation + bulk save) so stop-loss/
                # take-profit prices advance and the on_trade_*_updated
                # hooks fire — matches live behaviour (see
                # DefaultTradeOrderEvaluator.evaluate).
                self.trade_service.update(open_trade.id, update_data)

            self._check_take_profits()
            self._check_stop_losses()
