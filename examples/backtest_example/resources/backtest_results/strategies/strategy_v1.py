from pyindicators import ema, is_crossover, is_above, is_below, is_crossunder
from investing_algorithm_framework import TradingStrategy, TimeUnit, Context, \
    OrderSide

from .data_sources import bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker


class CrossOverStrategyV1(TradingStrategy):
    """
    A simple trading strategy that uses EMA crossovers to generate buy and
    sell signals. The strategy uses a 50-period EMA and a 100-period EMA
    to detect golden and death crosses. It also uses a 200-period EMA to
    determine the overall trend direction. The strategy trades BTC/EUR
    on a 2-hour timeframe. The strategy is designed to be used with the
    Investing Algorithm Framework and uses the PyIndicators library
    to calculate the EMAs and crossover signals.

    The strategy uses a trailing stop loss and take profit to manage
    risk. The stop loss is set to 5% below the entry price and the
    take profit is set to 10% above the entry price. The stop loss and
    take profit are both trailing, meaning that they will move up
    with the price when the price goes up.
    """
    time_unit = TimeUnit.HOUR
    interval = 2
    symbol_pairs = ["BTC/EUR"]
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]
    fast = 50
    slow = 100
    trend = 200
    stop_loss_percentage = 2
    stop_loss_sell_size = 50
    take_profit_percentage = 8
    take_profit_sell_size = 50

    def __init__(
        self,
        time_unit: TimeUnit = TimeUnit.HOUR,
        interval: int = 2,
        symbol_pairs: list[str] = None,
        market_data_sources=None,
        fast: int = 50,
        slow: int = 100,
        trend: int = 200,
        stop_loss_percentage: float = 2.0,
        stop_loss_sell_size: float = 50.0,
        take_profit_percentage: float = 8.0,
        take_profit_sell_size: float = 50.0
    ):
        super().__init__(
            time_unit=time_unit,
            interval=interval,
            market_data_sources=market_data_sources or self.market_data_sources
        )
        self.symbol_pairs = symbol_pairs or self.symbol_pairs
        self.fast = fast
        self.slow = slow
        self.trend = trend
        self.stop_loss_percentage = stop_loss_percentage
        self.stop_loss_sell_size = stop_loss_sell_size
        self.take_profit_percentage = take_profit_percentage
        self.take_profit_sell_size = take_profit_sell_size

    def apply_strategy(self, context: Context, market_data):

        for pair in self.symbol_pairs:
            symbol = pair.split('/')[0]

            # Don't trade if there are open orders for the symbol
            # This is important to avoid placing new orders while there are
            # existing orders that are not yet filled
            if context.has_open_orders(symbol):
                continue

            ohlcv_data = market_data[f"{pair}-ohlcv-2h"]
            # ticker_data = market_data[f"{symbol}-ticker"]
            # Add fast, slow, and trend EMAs to the data
            ohlcv_data = ema(
                ohlcv_data,
                source_column="Close",
                period=self.fast,
                result_column=f"ema_{self.fast}"
            )
            ohlcv_data = ema(
                ohlcv_data,
                source_column="Close",
                period=self.slow,
                result_column=f"ema_{self.slow}"
            )
            ohlcv_data = ema(
                ohlcv_data,
                source_column="Close",
                period=self.trend,
                result_column=f"ema_{self.trend}"
            )

            price = ohlcv_data["Close"][-1]

            if not context.has_position(symbol) \
                    and self._is_buy_signal(ohlcv_data):
                order = context.create_limit_order(
                    target_symbol=symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
                trade = context.get_trade(order_id=order.id)
                context.add_stop_loss(
                    trade=trade,
                    trade_risk_type="trailing",
                    percentage=self.stop_loss_percentage,
                    sell_percentage=self.stop_loss_sell_size
                )
                context.add_take_profit(
                    trade=trade,
                    percentage=self.take_profit_percentage,
                    trade_risk_type="trailing",
                    sell_percentage=self.take_profit_sell_size
                )

            if context.has_position(symbol) \
                    and self._is_sell_signal(ohlcv_data):
                open_trades = context.get_open_trades(
                    target_symbol=symbol
                )

                for trade in open_trades:
                    context.close_trade(trade)

    def _is_sell_signal(self, data):
        return is_crossunder(
            data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            number_of_data_points=2
        ) and is_below(
            data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.trend}",
        )

    def _is_buy_signal(self, data):
        return is_crossover(
            data=data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            number_of_data_points=2
        ) and is_above(
            data=data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.trend}",
        )
