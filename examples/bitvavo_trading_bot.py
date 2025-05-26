from dotenv import load_dotenv
import logging.config

from investing_algorithm_framework import TimeUnit, TradingStrategy, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, \
    create_app, DEFAULT_LOGGING_CONFIG, Context

"""
Bitvavo trading bot example with market data sources of bitvavo.
Bitvavo does not requires you to have an API key and secret key to access
their market data. If you just want to backtest your strategy,
you don't need to add a market credential. If your running your strategy live,
you need to add a market credential to the app, that accesses your
account on bitvavo.
"""

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

# Load the environment variables from the .env file
load_dotenv()

# Define your market data sources for coinbase
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="bitvavo",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="bitvavo",
    symbol="BTC/EUR",
)

class BitvavoTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 10
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def run_strategy(self, context: Context, market_data):
        print(market_data["BTC/EUR-ohlcv"])
        print(market_data["BTC/EUR-ticker"])

# Create an app and add the market data sources and market credentials to it
app = create_app()
app.add_strategy(BitvavoTradingStrategy)
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=400)

if __name__ == "__main__":
    app.run()
