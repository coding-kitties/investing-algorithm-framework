from dotenv import load_dotenv
import logging.config
from investing_algorithm_framework import MarketCredential, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, TradingStrategy, \
    create_app, PortfolioConfiguration, Algorithm, DEFAULT_LOGGING_CONFIG, \
    Context
"""
Coinbase market data sources example. Coinbase requires you to have an API key
and secret key to access their market data. You can create them here:
https://www.coinbase.com/settings/api

You need to add a market credential to the app, and then add market
data sources to the app. You can then use the market data
sources in your trading strategy.
"""

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

# Load the environment variables from the .env file
load_dotenv()

# Define your market credential for coinbase, keys are read from .env file
coinbase_market_credential = MarketCredential(
    market="coinbase",
)
# Define your market data sources for coinbase
coinbase_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="coinbase",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
coinbase_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="coinbase",
    symbol="BTC/EUR",
)


class BitvavoTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 10
    market_data_sources = [coinbase_btc_eur_ohlcv_2h, coinbase_btc_eur_ticker]

    def apply_strategy(self, context: Context, market_data):
        print(market_data["BTC/EUR-ohlcv"])
        print(market_data["BTC/EUR-ticker"])

# Create an algorithm and link your trading strategy to it
algorithm = Algorithm()
algorithm.add_strategy(BitvavoTradingStrategy)

# Create an app and add the market data sources and market credentials to it
app = create_app()
app.add_market_credential(coinbase_market_credential)

# Register your algorithm and portfolio configuration to the app
app.add_algorithm(algorithm)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        initial_balance=41,
        trading_symbol="EUR",
        market="coinbase"
    )
)

if __name__ == "__main__":
    app.run()
