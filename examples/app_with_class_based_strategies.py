from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, TradingTimeFrame, TradingDataType, TradingStrategy


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 3
    trading_data_type = TradingDataType.OHLCV
    trading_time_frame_start_date = datetime.utcnow() - timedelta(days=1)
    trading_time_frame = TradingTimeFrame.ONE_MINUTE
    market = "BITVAVO"
    symbols = ["BTC/EUR"]

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        print(len(algorithm.get_orders()))
        print(market_data)


# No resource directory specified, so an in-memory database will be used
app = create_app()
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
