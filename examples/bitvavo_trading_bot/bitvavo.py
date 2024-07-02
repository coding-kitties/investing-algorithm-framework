import os

from investing_algorithm_framework import MarketCredential, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, TradingStrategy, \
    create_app, PortfolioConfiguration, Algorithm, SYMBOLS, RESOURCE_DIRECTORY

"""
Bitvavo trading bot example with market data sources of bitvavo.
Bitvavo does not requires you to have an API key and secret key to access 
their market data. If you just want to backtest your strategy, 
you don't need to add a market credential. If your running your strategy live,
you need to add a market credential to the app, that accesses your 
account on bitvavo.
"""


# Define your market credential for bitvavo
bitvavo_market_credential = MarketCredential(
    api_key="<your_api_key>",
    secret_key="<your_secret_key>",
    market="bitvavo",
)
# Define your market data sources for coinbase
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="bitvavo",
    symbol="BTC/EUR",
    timeframe="2h",
    window_size=200
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="bitvavo",
    symbol="BTC/EUR",
)


class BitvavoTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def apply_strategy(self, algorithm, market_data):
        print(market_data["BTC/EUR-ohlcv"])
        print(market_data["BTC/EUR-ticker"])


config = {
    SYMBOLS: ["BTC/EUR"],
    RESOURCE_DIRECTORY: os.path.join(os.path.dirname(__file__), "resources")
}

# Create an algorithm and link your trading strategy to it
algorithm = Algorithm()
algorithm.add_strategy(BitvavoTradingStrategy)

# Create an app and add the market data sources and market credentials to it
app = create_app(config=config)
app.add_market_credential(bitvavo_market_credential)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)

# Register your algorithm and portfolio configuration to the app
app.add_algorithm(algorithm)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        initial_balance=1000,
        trading_symbol="EUR",
        market="bitvavo"
    )
)

if __name__ == "__main__":
    app.run()
