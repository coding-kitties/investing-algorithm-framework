from datetime import datetime, timedelta
from investing_algorithm_framework import MarketCredential, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, TradingStrategy, \
    create_app, PortfolioConfiguration

"""
Coinbase market data sources example. Coinbase requires you to have an API key
and secret key to access their market data. You can create them here:
https://www.coinbase.com/settings/api

You need to add a market credential to the app, and then add market data sources
to the app. You can then use the market data sources in your trading strategy.
"""
# Define your market credential for coinbase
coinbase_market_credential = MarketCredential(
    api_key="<coinbase_api_key>",
    secret_key="<coinbase_secret_key>",
    market="coinbase",
)
# Define your market data sources for coinbase
coinbase_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="coinbase",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda: datetime.utcnow() - timedelta(days=17)
)
coinbase_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="coinbase",
    symbol="BTC/EUR",
)


class CoinBaseTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker"
    ]

    def apply_strategy(self, algorithm, market_data):
        print(market_data["BTC/EUR-ohlcv"])
        print(market_data["BTC/EUR-ticker"])


app = create_app()
app.add_market_credential(coinbase_market_credential)
app.add_market_data_source(coinbase_btc_eur_ohlcv_2h)
app.add_market_data_source(coinbase_btc_eur_ticker)
app.add_strategy(CoinBaseTradingStrategy)
app.add_portfolio_configuration(PortfolioConfiguration(
    initial_balance=1000,
    trading_symbol="EUR",
    market="coinbase"
))

if __name__ == "__main__":
    app.run()

