import os

from investing_algorithm_framework import App, TimeUnit, AlgorithmContext, \
    TradingDataTypes
from investing_algorithm_framework.configuration.constants import BINANCE, \
    BINANCE_API_KEY, BINANCE_SECRET_KEY, TRADING_SYMBOL

dir_path = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

# Create an application (manages your algorithm, rest api, etc...)
app = App(
    config={
        BINANCE_API_KEY: "<BINANCE_API_KEY>",
        BINANCE_SECRET_KEY: "<BINANCE_SECRET_KEY>",
        TRADING_SYMBOL: "USDT",
    }
)


@app.algorithm.strategy(
    time_unit=TimeUnit.SECONDS,
    interval=5,
    data_provider_identifier=BINANCE,
    target_symbol="BTC",
    trading_data_type=TradingDataTypes.TICKER,
)
def perform_strategy(context: AlgorithmContext, ticker, **kwargs):
    print("hello")


def lambda_handler(event, context):
    app.start(event, context)
