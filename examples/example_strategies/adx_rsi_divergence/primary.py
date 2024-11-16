import tulipy as tp

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, Algorithm

# Ohlcv data source
btc_eur_ohlcv_data = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_ohlcv",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="2h",
    window_size=200,
)

# Ticker data source
btc_eur_ticker_data = CCXTTickerMarketDataSource(
    identifier="BTC/EUR_ticker",
    symbol="BTC/EUR",
    market="BITVAVO",
    backtest_timeframe="2h"
)


class RSIADXStrategy(TradingStrategy):
    """
    Implementation of TradingStrategy that uses RSI and ADX metrics.
    The strategy is parameterized in order to do experiments with it.
    This allows you to test the strategy with different configurations.
    """
    market_data_sources = [btc_eur_ohlcv_data, btc_eur_ticker_data]
    symbols = ["BTC/EUR"]
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        rsi_period=14,
        adx_period=14,
        rsi_buy_threshold=50,
        rsi_sell_threshold=50,
        adx_buy_threshold=35,
        adx_sell_threshold=35,
    ):
        super(RSIADXStrategy, self).__init__()
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.adx_buy_threshold = adx_buy_threshold
        self.adx_sell_threshold = adx_sell_threshold

    def apply_strategy(self, algorithm, market_data):

        for symbol in self.symbols:
            ohlcv_df = market_data[f"{symbol}_ohlcv"]
            rsi = tp.rsi(ohlcv_df["Close"].to_numpy(), period=self.rsi_period)
            close = ohlcv_df["Close"].to_numpy()
            pdi, ndi = tp.di(
                high=ohlcv_df["High"].to_numpy(),
                low=ohlcv_df["Low"].to_numpy(),
                close=close,
                period=self.adx_period
            )
            adx = tp.adx(
                high=ohlcv_df["High"].to_numpy(),
                low=ohlcv_df["Low"].to_numpy(),
                close=close,
                period=self.adx_period
            )
            target_symbol = symbol.split("/")[0]
            price = close[-1]

            if self.is_buy_signal(
                    symbol=target_symbol,
                    algorithm=algorithm,
                    adx=adx[-1],
                    pdi=pdi[-1],
                    ndi=ndi[-1],
                    rsi=rsi[-1]
            ):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side="BUY",
                    price=price,
                    percentage_of_portfolio=20,
                    precision=4
                )
            elif self.is_sell_signal(
                    symbol=target_symbol,
                    algorithm=algorithm,
                    adx=adx[-1],
                    pdi=pdi[-1],
                    ndi=ndi[-1],
                    rsi=rsi[-1]
            ):
                algorithm.close_position(
                    symbol=target_symbol
                )

    def is_buy_signal(self, symbol, algorithm, adx, pdi, ndi, rsi):

        if algorithm.has_open_orders(symbol):
            return False

        if algorithm.has_position(symbol):
            return False

        # if adx >= self.adx_buy_threshold and rsi <= self.rsi_buy_threshold:
        #     return True

        if adx >= self.adx_buy_threshold and pdi < ndi \
                and rsi <= self.rsi_buy_threshold:
            return True

    def is_sell_signal(self, symbol, algorithm, adx, pdi, ndi, rsi):

        if algorithm.has_open_orders(symbol):
            return False

        if not algorithm.has_position(symbol):
            return False

        if adx >= self.adx_sell_threshold and pdi > ndi \
                and rsi >= self.rsi_sell_threshold:
            return True


def create_algorithm(
    name,
    context,
    rsi_period=14,
    adx_period=14,
    rsi_buy_threshold=50,
    rsi_sell_threshold=50,
    adx_buy_threshold=35,
    adx_sell_threshold=35,
):
    algorithm = Algorithm(
        name=name,
        context=context,
        strategy=RSIADXStrategy(
            rsi_period=rsi_period,
            adx_period=adx_period,
            rsi_buy_threshold=rsi_buy_threshold,
            rsi_sell_threshold=rsi_sell_threshold,
            adx_buy_threshold=adx_buy_threshold,
            adx_sell_threshold=adx_sell_threshold,
        ),
        data_sources=[btc_eur_ohlcv_data, btc_eur_ticker_data],
    )
    return algorithm
