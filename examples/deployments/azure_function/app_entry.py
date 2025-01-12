from dotenv import load_dotenv

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, CCXTOHLCVMarketDataSource, Algorithm, \
    CCXTTickerMarketDataSource, MarketCredential, AzureBlobStorageStateHandler

load_dotenv()

# Define market data sources OHLCV data for candles
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
app = create_app(state_handler=AzureBlobStorageStateHandler())
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
algorithm = Algorithm()
app.add_market_credential(MarketCredential(market="bitvavo"))
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo",
        trading_symbol="EUR",
        initial_balance=20
    )
)
app.add_algorithm(algorithm)

@algorithm.strategy(
    # Run every two hours
    time_unit=TimeUnit.HOUR,
    interval=2,
    # Specify market data sources that need to be passed to the strategy
    market_data_sources=[bitvavo_btc_eur_ticker, "BTC-ohlcv"]
)
def perform_strategy(algorithm: Algorithm, market_data: dict):
    # By default, ohlcv data is passed as polars df in the form of
    # {"<identifier>": <dataframe>}  https://pola.rs/,
    # call to_pandas() to convert to pandas
    polars_df = market_data["BTC-ohlcv"]
    print(f"I have access to {len(polars_df)} candles of ohlcv data")
