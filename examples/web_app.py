import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, TradingTimeFrame, TradingDataType

app = create_app(
    {RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()}, web=True
)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        trading_symbol="<your_trading_symbol>"
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
    print(len(algorithm.get_orders()))
    print(market_data)


if __name__ == "__main__":
    app.run()
