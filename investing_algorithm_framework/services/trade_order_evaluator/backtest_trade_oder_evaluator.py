from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import Trade, Order, TradeStatus
from investing_algorithm_framework.domain.native_event import \
    native_event_engine
from .trade_order_evaluator import TradeOrderEvaluator


class BacktestTradeOrderEvaluator(TradeOrderEvaluator):
    """
    Event-backtest trade/order evaluator.

    The shared base class owns Python candle matching, trading costs and
    fill side effects. This subclass optionally delegates candle selection
    to Rust, while keeping sequential fill application and hooks in Python.
    """

    def __init__(self, *args, event_fill_backend="python", **kwargs):
        super().__init__(*args, **kwargs)
        if event_fill_backend not in ("python", "rust", "auto"):
            raise ValueError('event_fill_backend must be python, rust or auto')
        self.event_fill_backend = event_fill_backend
        self._native_fills = None
        if event_fill_backend != 'python':
            from .native import (
                NativeEventFillUnsupported, load_native_event_fills,
            )
            try:
                self._native_fills = load_native_event_fills()
            except (ImportError, NativeEventFillUnsupported):
                if event_fill_backend == 'rust':
                    raise

    def _check_has_executed(self, order, ohlcv_df):
        native = native_event_engine() or self._native_fills
        if native is None:
            return super()._check_has_executed(order, ohlcv_df)
        if ohlcv_df.is_empty():
            return
        from .native import NativeEventFillUnsupported, select_native_fill

        try:
            trigger, fill, market = select_native_fill(
                native, order, ohlcv_df,
            )
        except NativeEventFillUnsupported:
            if native_event_engine() is not None \
                    or self.event_fill_backend == 'rust':
                raise
            return super()._check_has_executed(order, ohlcv_df)
        if trigger is not None:
            order.set_triggered_at(ohlcv_df['Datetime'][trigger])
            self.order_service.repository.update(
                order.id, {'triggered_at': order.get_triggered_at()},
            )
        if fill is not None:
            base_price = order.price
            if market:
                base_price = (order.get_stop_price() if trigger is not None
                              else ohlcv_df['Open'][fill])
            volume = (ohlcv_df['Volume'][fill]
                      if 'Volume' in ohlcv_df.columns else None)
            self._apply_fill(order, base_price, order.order_side, volume,
                             is_market_order=market)

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
        native = native_event_engine()
        if native is not None:
            return native.evaluate_event_market(self, open_orders, ohlcv_data)
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

                self._mark_market_trade(open_trade, data)

            self._check_take_profits()
            self._check_stop_losses()

    def _mark_market_trade(self, trade, data):
        last_row = data.tail(1)
        self.trade_service.update(trade.id, {
            'last_reported_price': last_row['Close'][0],
            'last_reported_price_datetime': last_row['Datetime'][0],
            'updated_at': last_row['Datetime'][0],
        })
