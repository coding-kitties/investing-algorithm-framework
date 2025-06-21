import logging.config
from dotenv import load_dotenv

from investing_algorithm_framework import create_app, TimeUnit, Context, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, DEFAULT_LOGGING_CONFIG, TradingStrategy

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

# OHLCV data for candles
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
# Ticker data for orders, trades and positions
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

app = create_app()
# Registered bitvavo market, credentials are read from .env file by default
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=100)

class MyStrategy(TradingStrategy):
    interval = 2
    time_unit = TimeUnit.HOUR
    data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def run_strategy(self, context: Context, market_data):
        # Access the data sources with the indentifier
        polars_df = market_data["BTC-ohlcv"]
        ticker_data = market_data["BTC-ticker"]
        unallocated_balance = context.get_unallocated()
        positions = context.get_positions()
        trades = context.get_trades()
        open_trades = context.get_open_trades()
        closed_trades = context.get_closed_trades()

if __name__ == "__main__":
    app.run()
