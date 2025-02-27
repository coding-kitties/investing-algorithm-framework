import logging.config
from dotenv import load_dotenv

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, CCXTOHLCVMarketDataSource, Context, CCXTTickerMarketDataSource, \
    MarketCredential, DEFAULT_LOGGING_CONFIG, Algorithm, Context

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

# OHLCV data for candles
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
# Ticker data for orders, trades and positions
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)
app = create_app(web=True)

# Bitvavo market credentials are read from .env file, or you can
# set them  manually as params
app.add_market_credential(MarketCredential(market="bitvavo"))
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo", trading_symbol="EUR", initial_balance=40
    )
)

algorithm = Algorithm(name="test_algorithm")

# Define a strategy for the algorithm that will run every 10 seconds
@algorithm.strategy(
    time_unit=TimeUnit.SECOND,
    interval=10,
    market_data_sources=[bitvavo_btc_eur_ticker, bitvavo_btc_eur_ohlcv_2h]
)
def perform_strategy(context: Context, market_data: dict):
    # Access the data sources with the indentifier
    polars_df = market_data["BTC-ohlcv"]
    ticker_data = market_data["BTC-ticker"]
    unallocated_balance = context.get_unallocated()
    positions = context.get_positions()
    trades = context.get_trades()
    open_trades = context.get_open_trades()
    closed_trades = context.get_closed_trades()

app.add_algorithm(algorithm)

if __name__ == "__main__":
    app.run()