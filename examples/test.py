import logging.config
from dotenv import load_dotenv

from pyindicators import ema, rsi

from investing_algorithm_framework import create_app, TimeUnit, Context, BacktestDateRange, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, DEFAULT_LOGGING_CONFIG, \
    TradingStrategy, SnapshotInterval, convert_polars_to_pandas

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
logger = logging.getLogger(__name__)

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

app = create_app()
# Registered bitvavo market, credentials are read from .env file by default
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=100)

class MyStrategy(TradingStrategy):
    interval = 2
    time_unit = TimeUnit.HOUR
    data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def run_strategy(self, context: Context, market_data):

        if context.has_open_orders(target_symbol="BTC"):
            logger.info("There are open orders, skipping strategy iteration.")
            return

        print(market_data)

        data = convert_polars_to_pandas(market_data["BTC-ohlcv"])
        data = ema(data, source_column="Close", period=20, result_column="ema_20")
        data = ema(data, source_column="Close", period=50, result_column="ema_50")
        data = ema(data, source_column="Close", period=100, result_column="ema_100")
        data = rsi(data, source_column="Close", period=14, result_column="rsi_14")

        if context.has_position("BTC") and self.sell_signal(data):
            context.create_limit_sell_order(
                "BTC", percentage_of_position=100, price=data["Close"].iloc[-1]
            )
            return

        if not context.has_position("BTC") and self.buy_signal(data):
            context.create_limit_buy_order(
                "BTC", percentage_of_portfolio=20, price=data["Close"].iloc[-1]
            )
            return

    def buy_signal(self, data):
        if len(data) < 100:
            return False
        last_row = data.iloc[-1]
        if last_row["ema_20"] > last_row["ema_50"] and last_row["ema_50"] > last_row["ema_100"]:
            return True
        return False

    def sell_signal(self, data):

        if data["ema_20"].iloc[-1] < data["ema_50"].iloc[-1] and \
           data["ema_20"].iloc[-2] >= data["ema_50"].iloc[-2]:
            return True

        return False

date_range = BacktestDateRange(
    start_date="2023-08-24 00:00:00", end_date="2023-12-02 00:00:00"
)
app.add_strategy(MyStrategy)

if __name__ == "__main__":
    # Run the backtest with a daily snapshot interval for end-of-day granular reporting
    backtest_report = app.run_backtest(
        backtest_date_range=date_range, initial_amount=100, snapshot_interval=SnapshotInterval.STRATEGY_ITERATION
    )
    backtest_report.show()