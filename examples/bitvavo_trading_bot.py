from dotenv import load_dotenv
import logging.config

from investing_algorithm_framework import TimeUnit, TradingStrategy, \
    create_app, DEFAULT_LOGGING_CONFIG, Context, DataSource

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

# Define your bitvavo trading strategy and register the data sources
class BitvavoTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 10
    data_sources = [
        DataSource(data_type="OHLCV", market="bitvavo", symbol="BTC/EUR", window_size=200, time_frame="2h", identifier="BTC/EUR-ohlcv"),
        DataSource(data_type="Ticker", market="bitvavo", symbol="BTC/EUR", identifier="BTC/EUR-ticker")
    ]

    def run_strategy(self, context: Context, data):
        print(data["BTC/EUR-ohlcv"])
        print(data["BTC/EUR-ticker"])

# Create an app and add the market data sources and market credentials to it
app = create_app()
app.add_strategy(BitvavoTradingStrategy)

# Market credentials for bitvavo for both the portfolio connection and data sources will
# be read from .env file, when not registering a market credential object in the app.
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=400)

if __name__ == "__main__":
    app.run()
