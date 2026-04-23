from typing import List, Dict

import polars as pl

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    Trade, Order, TradeStatus, TradingCost, OrderType
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

        When a blotter is available (via the parent TradeOrderEvaluator),
        fill pricing, commission, and fill amounts are delegated to the
        blotter's models. Otherwise, TradingCost is used as a fallback.

        BUY ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the lowest low price of the series is below or equal
            to the order price, the order is filled.

        SELL ORDER filled Rules:
        - Only uses prices after the last update_at of the order.
        - If the highest high price of the series is above or equal
            to the order price, the order is filled.

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

        # Market orders: fill at the open of the first available candle
        if OrderType.MARKET.equals(order.order_type):
            first_candle = ohlcv_data_after_order.head(1)
            base_price = first_candle["Open"][0]
            volume = (
                first_candle["Volume"][0]
                if "Volume" in first_candle.columns
                else None
            )
            self._apply_fill(
                order, base_price, order_side, volume,
                is_market_order=True
            )
            return

        # Limit orders: check if OHLCV data triggers a fill
        if OrderSide.BUY.equals(order_side):
            fill_candles = ohlcv_data_after_order.filter(
                pl.col('Low') <= order_price
            )
        elif OrderSide.SELL.equals(order_side):
            fill_candles = ohlcv_data_after_order.filter(
                pl.col('High') >= order_price
            )
        else:
            return

        if fill_candles.is_empty():
            return

        first_fill = fill_candles.head(1)
        volume = (
            first_fill["Volume"][0]
            if "Volume" in first_fill.columns
            else None
        )
        self._apply_fill(
            order, order_price, order_side, volume,
            is_market_order=False
        )

    def _apply_fill(
        self, order, base_price, order_side, volume,
        is_market_order=False
    ):
        """
        Apply a fill to an order, using blotter methods when available
        or falling back to TradingCost.

        Supports partial fills when the blotter's fill model limits
        the fillable amount (e.g. VolumeBasedFill).
        """
        remaining = (
            order.remaining
            if order.remaining is not None
            else order.amount
        )

        if self._blotter is not None:
            fill_price = self._blotter.get_fill_price(
                base_price, order_side, remaining, volume
            )
            fill_amount = min(
                self._blotter.get_fill_amount(remaining, volume),
                remaining
            )
            if OrderSide.BUY.equals(order_side):
                slippage = fill_price - base_price
            else:
                slippage = base_price - fill_price
            fee = self._blotter.on_fill(
                order.id, order.symbol, order_side,
                fill_price, base_price, fill_amount,
            )
            fee_rate = self._blotter.get_commission_rate()
        else:
            tc = self._resolve_trading_cost(order.symbol)
            if OrderSide.BUY.equals(order_side):
                fill_price = tc.get_buy_fill_price(base_price)
                slippage = fill_price - base_price
            else:
                fill_price = tc.get_sell_fill_price(base_price)
                slippage = base_price - fill_price
            fill_amount = remaining
            fee = tc.get_fee(fill_price * fill_amount)
            fee_rate = (
                tc.fee_percentage / 100 if tc.fee_percentage else None
            )

        if fill_amount <= 0:
            return

        new_filled = (order.filled or 0) + fill_amount
        new_remaining = order.amount - new_filled
        accumulated_fee = (order.order_fee or 0) + fee

        if new_remaining <= 0:
            # Full fill
            update_data = {
                'status': OrderStatus.CLOSED.value,
                'remaining': 0,
                'filled': order.amount,
                'price': fill_price,
                'order_fee': accumulated_fee,
                'slippage': slippage,
            }
            if fee_rate is not None:
                update_data['order_fee_rate'] = fee_rate
        else:
            # Partial fill — order stays open for next evaluation
            update_data = {
                'filled': new_filled,
                'remaining': new_remaining,
                'order_fee': accumulated_fee,
            }

        # Market order portfolio reconciliation
        if is_market_order and new_remaining <= 0:
            estimated_price = order.estimated_price

            if estimated_price is not None:
                price_delta = fill_price - estimated_price
                cost_adjustment = price_delta * order.amount

                if cost_adjustment != 0:
                    position = self.order_service.position_service.get(
                        order.position_id
                    )
                    portfolio = \
                        self.order_service.portfolio_repository.get(
                            position.portfolio_id
                        )

                    if OrderSide.BUY.equals(order_side):
                        new_unallocated = \
                            portfolio.get_unallocated() - cost_adjustment
                        self.order_service.portfolio_repository.update(
                            portfolio.id,
                            {"unallocated": new_unallocated}
                        )
                        trading_position = \
                            self.order_service.position_service.find(
                                {
                                    "symbol": portfolio.trading_symbol,
                                    "portfolio": portfolio.id
                                }
                            )
                        self.order_service.position_service.update(
                            trading_position.id,
                            {
                                "amount":
                                    trading_position.get_amount()
                                    - cost_adjustment
                            }
                        )

        self.order_service.update(order.id, update_data)
