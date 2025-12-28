from dotenv import load_dotenv
from typing import Dict, Any
import logging.config

from investing_algorithm_framework import TimeUnit, \
    DataSource, TradingStrategy, create_app, DEFAULT_LOGGING_CONFIG, Context
"""
Coinbase trading bot example. Coinbase requires you to have an API key
and secret key to access their market data. You can create them here:
https://www.coinbase.com/settings/api
"""

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

# Load the environment variables from the .env file
load_dotenv()

# Define your coinbase trading strategy and register the data sources
class CoinbaseTradingStrategy(TradingStrategy):
    algorithm_id = "coinbase-trading-strategy"
    time_unit = TimeUnit.SECOND
    interval = 10
    data_sources = [
        DataSource(data_type="OHLCV", market="coinbase", symbol="BTC/EUR", window_size=200, time_frame="2h", identifier="BTC/EUR-ohlcv"),
        DataSource(data_type="Ticker", market="coinbase", symbol="BTC/EUR", identifier="BTC/EUR-ticker")
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]):
        print(data["BTC/EUR-ohlcv"])
        print(data["BTC/EUR-ticker"])

# Create an app and configure it with coinbase
app = create_app()
app.add_strategy(CoinbaseTradingStrategy)

# Market credentials for coinbase for both the portfolio connection and data sources will
# be read from .env file, when not registering a market credential object in the app.
app.add_market(market="coinbase", trading_symbol="EUR", initial_balance=400)

if __name__ == "__main__":
    app.run()
