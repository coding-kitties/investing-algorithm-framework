from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, CCXTOHLCVMarketDataSource, TradingStrategy, Task, \
    CCXTTickerMarketDataSource, MarketCredential


# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda : datetime.utcnow() - timedelta(days=17)
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)


class CustomTask(Task):
    time_unit = TimeUnit.SECOND
    interval = 5
    market_data_sources = ["BTC/EUR-ohlcv", "BTC/EUR-ticker"]

    def run(self, algorithm):
        pass

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 3
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def apply_strategy(self, algorithm, market_data):
        pass


# No resource directory specified, so an in-memory database will be used
app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        trading_symbol="<your_trading_symbol>"
    )
)
app.add_market_credential(
    MarketCredential(
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        market="<your_market>"
    )
)
app.add_strategy(MyTradingStrategy)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)

if __name__ == "__main__":
    app.run()
