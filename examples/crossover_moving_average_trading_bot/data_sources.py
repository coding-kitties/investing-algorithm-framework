from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    CCXTTickerMarketDataSource


bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="BINANCE",
    symbol="BTC/EUR",
    timeframe="2h",
    window_size=200
)
bitvavo_dot_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="DOT/EUR-ohlcv",
    market="BINANCE",
    symbol="DOT/EUR",
    timeframe="2h",
    window_size=200
)
bitvavo_dot_eur_ticker = CCXTTickerMarketDataSource(
    identifier="DOT/EUR-ticker",
    market="BINANCE",
    symbol="DOT/EUR",
    backtest_timeframe="2h",
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="BINANCE",
    symbol="BTC/EUR",
    backtest_timeframe="2h",
)
