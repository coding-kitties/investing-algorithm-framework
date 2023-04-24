import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, TradingTimeFrame, TradingDataType

app = create_app(
    {RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()},
    stateless=True
)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="binance",
        api_key="xxxxxx",
        secret_key="xxxxxx",
        trading_symbol="USDT"
    )
)


@app.strategy(
    time_unit=TimeUnit.SECOND,
    interval=5,
    market="BINANCE",
    symbols=["BTC/USDT"],
    trading_data_types=[TradingDataType.OHLCV],
    trading_time_frame_start_date=datetime.utcnow() - timedelta(days=1),
    trading_time_frame=TradingTimeFrame.ONE_MINUTE
)
def perform_strategy(algorithm, market_data):
    print(algorithm.get_allocated())
    print(algorithm.get_unallocated())
    print(market_data)

