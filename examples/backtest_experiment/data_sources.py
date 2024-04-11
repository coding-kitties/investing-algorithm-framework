[
    {
        "name": "9-50-100",
        "description": "9-50-100",
        "fast": 9,
        "slow": 50,
        "trend": 100,
        "stop_loss_percentage": 7
    },
    {
        "name": "10-50-100",
        "description": "10-50-100",
        "fast": 10,
        "slow": 50,
        "trend": 100,
        "stop_loss_percentage": 7
    },
    {
        "name": "11-50-100",
        "description": "11-50-100",
        "fast": 11,
        "slow": 50,
        "trend": 100,
        "stop_loss_percentage": 7
    },
    {
        "name": "9-75-150",
        "description": "9-75-150",
        "fast": 9,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "10-75-150",
        "description": "10-75-150",
        "fast": 10,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "11-75-150",
        "description": "11-75-150",
        "fast": 11,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "20-75-150",
        "description": "20-75-150",
        "fast": 20,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "21-75-150",
        "description": "21-75-150",
        "fast": 21,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "22-75-150",
        "description": "22-75-150",
        "fast": 22,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "23-75-150",
        "description": "23-75-150",
        "fast": 23,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "24-75-150",
        "description": "24-75-150",
        "fast": 24,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "25-75-150",
        "description": "25-75-150",
        "fast": 25,
        "slow": 75,
        "trend": 150,
        "stop_loss_percentage": 7
    },
    {
        "name": "20-75-200",
        "description": "20-75-200",
        "fast": 20,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    },
    {
        "name": "21-75-200",
        "description": "24-75-200",
        "fast": 24,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    },
    {
        "name": "22-75-200",
        "description": "24-75-200",
        "fast": 24,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    },
    {
        "name": "23-75-200",
        "description": "24-75-200",
        "fast": 24,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    },
    {
        "name": "24-75-200",
        "description": "24-75-200",
        "fast": 24,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    },
    {
        "name": "25-75-150",
        "description": "25-75-200",
        "fast": 25,
        "slow": 75,
        "trend": 200,
        "stop_loss_percentage": 7
    }
]
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
