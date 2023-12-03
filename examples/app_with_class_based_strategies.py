import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, CCXTOHLCVMarketDataSource, TradingStrategy, RESOURCE_DIRECTORY


def start_date_func():
    return datetime.utcnow() - timedelta(days=17)

# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=start_date_func
)


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 3
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h]

    def apply_strategy(self, algorithm, market_data):
        pass


# No resource directory specified, so an in-memory database will be used
app = create_app(
    config={RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()}
)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        trading_symbol="EUR"
    )
)
app.add_strategy(MyTradingStrategy)

if __name__ == "__main__":
    app.run()
