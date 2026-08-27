from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import Trade, Order, \
    INDEX_DATETIME, TradeStatus, TradingCost
from .trade_order_evaluator import TradeOrderEvaluator

# Prefix PaperTradingOrderExecutor stamps onto every order's
# external_id — used here (and only here) to identify which open
# orders are local paper-trading orders, so their fills can be
# validated locally against OHLCV data instead of relying on
# check_pending_orders() (which only makes sense for orders a real
# broker/sandbox is tracking).
_PAPER_ORDER_EXTERNAL_ID_PREFIX = "paper-"


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
        # Real/broker-sandbox orders: ask the venue for fresh state.
        self.order_service.check_pending_orders()

        # Local paper-trading orders: PaperTradingOrderExecutor leaves
        # these OPEN instead of instant-filling them, so validate them
        # against OHLCV data the same way BacktestTradeOrderEvaluator
        # validates backtest orders — a real broker never "confirms"
        # these, so nothing above touches them.
        for open_order in open_orders:
            if not self._is_local_paper_order(open_order):
                continue

            data = ohlcv_data.get(open_order.symbol)

            if data is None or data.is_empty():
                continue

            self._check_has_executed(open_order, data)

        current_date = self.configuration_service.config[INDEX_DATETIME]

        # Re-query open trades to include any trades created by the
        # paper-order fills simulated above (mirrors
        # BacktestTradeOrderEvaluator.evaluate).
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
                last_row_date = last_row["Datetime"][0]
                update_data = {
                    "last_reported_price": last_row["Close"][0],
                    "last_reported_price_datetime": last_row_date,
                    "updated_at": current_date
                }
                # Route through TradeService.update() (not a direct
                # domain-object mutation + bulk save) so stop-loss/
                # take-profit prices advance and the on_trade_*_updated
                # hooks fire — matches the documented per-iteration
                # price-tracking behaviour (docs/architecture/
                # orders_and_trades/trades.md §8).
                self.trade_service.update(open_trade.id, update_data)

            self._check_take_profits()
            self._check_stop_losses()

    @staticmethod
    def _is_local_paper_order(order) -> bool:
        external_id = order.get_external_id()
        return bool(
            external_id
            and external_id.startswith(_PAPER_ORDER_EXTERNAL_ID_PREFIX)
        )

    def _resolve_paper_market(self, order):
        """
        Best-effort resolve the market (exchange id) an order's
        portfolio trades on, e.g. "bitvavo". Returns ``None`` rather
        than raising if it can't be resolved for any reason — cost
        estimation should never break order evaluation.
        """
        try:
            position = self.order_service.position_service.get(
                order.position_id
            )
            portfolio = self.order_service.portfolio_repository.get(
                position.portfolio_id
            )
            return portfolio.market
        except Exception:
            return None

    def _resolve_trading_cost(self, symbol, order=None):
        """
        Same resolution as the base class (per-symbol strategy
        ``TradingCost`` > market-level ``PortfolioConfiguration``
        defaults), but for local paper-trading orders that don't
        match either, falls back to the exchange's real, publicly
        advertised taker fee (via ccxt) instead of a zero-cost
        default — a much more realistic estimate for paper trading.
        """
        tc = super()._resolve_trading_cost(symbol, order=order)

        if order is None or not self._is_local_paper_order(order):
            return tc

        if tc.fee_percentage or tc.slippage_percentage \
                or tc.slippage_model:
            return tc

        market = self._resolve_paper_market(order)

        if market is None:
            return tc

        # Local import: avoids a circular import at module load time
        # (infrastructure -> services -> trade_order_evaluator).
        from investing_algorithm_framework.infrastructure \
            .order_executors.paper_trading_order_executor import (
                resolve_ccxt_taker_fee_percentage,
            )
        fee_percentage = resolve_ccxt_taker_fee_percentage(
            market, order.get_symbol()
        )

        if fee_percentage is None:
            return tc

        return TradingCost(symbol=symbol, fee_percentage=fee_percentage)
