import os

from investing_algorithm_framework import MarketCredential, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, TradingStrategy, \
    create_app, PortfolioConfiguration, Algorithm, SYMBOLS, RESOURCE_DIRECTORY

"""
Coinbase market data sources example. Coinbase requires you to have an API key
and secret key to access their market data. You can create them here:
https://www.coinbase.com/settings/api

You need to add a market credential to the app, and then add market
data sources to the app. You can then use the market data
sources in your trading strategy.
"""
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


class CoinBaseTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 5
    market_data_sources = [coinbase_btc_eur_ticker, coinbase_btc_eur_ohlcv_2h]

    def apply_strategy(self, algorithm, market_data):
        pass

algorithm = Algorithm()
algorithm.add_strategy(CoinBaseTradingStrategy)
app = create_app()
app.add_algorithm(algorithm)
app.add_market_credential(coinbase_market_credential)
app.add_portfolio_configuration(PortfolioConfiguration(
    initial_balance=1000,
    trading_symbol="EUR",
    market="coinbase"
))

if __name__ == "__main__":
    app.run()
