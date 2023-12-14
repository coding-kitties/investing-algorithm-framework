from datetime import datetime, timedelta
from investing_algorithm_framework import MarketCredential, TimeUnit, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, TradingStrategy, \
    create_app, PortfolioConfiguration

"""
Bitvavo market data sources example. Bitvavo does not requires you 
to have an API key and secret key to access their market data

If you just want to backtest your strategy, you don't need to 
add a market credential. If your runnning your strategy live,
you need to add a market credential to the app, that accesses your 
account on bitvavo.
"""
# Define your market credential for coinbase
bitvavo_market_credential = MarketCredential(
    api_key="WaLvaJ89SPUFDGqf",
    secret_key="DKAHZromFfshQQkEhp1QBzpSJfsY3k3U",
    market="bitvavo",
)
# Define your market data sources for coinbase
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="bitvavo",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda: datetime.utcnow() - timedelta(days=17)
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="bitvavo",
    symbol="BTC/EUR",
)


class BitvavoTradingStrategy(TradingStrategy):
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
app.add_market_credential(bitvavo_market_credential)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_strategy(BitvavoTradingStrategy)
app.add_portfolio_configuration(PortfolioConfiguration(
    initial_balance=1000,
    trading_symbol="EUR",
    market="bitvavo"
))

if __name__ == "__main__":
    app.run()

