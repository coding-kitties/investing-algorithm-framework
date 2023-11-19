from investing_algorithm_framework.domain import TradingDataType, \
    OperationalException, TradingTimeFrame, DATETIME_FORMAT, StrategyProfile
from datetime import datetime, timedelta


class MarketDataService:

    def __init__(self, market_service):
        self.market_service = market_service

    def get_data_for_backtest(self, to_timestamp, strategy_profile: StrategyProfile):
        self.market_service.market = strategy_profile.market
        return {"ohlcvs": self.market_service.get_ohclvs(
            strategy_profile.symbols,
            time_frame=strategy_profile.trading_time_frame,
            from_timestamp=strategy_profile.backtest_start_date_data,
            to_timestamp=to_timestamp
        )}

    def get_data_for_strategy(self, strategy, start_date=None, end_date=None):
        data = {}

        if strategy.market and \
                (strategy.trading_data_types or strategy.trading_data_type):
            self.market_service.market = strategy.market

            if not strategy.trading_data_types:
                strategy.trading_data_types = [strategy.trading_data_type]

            for trading_data_type in strategy.trading_data_types:

                if TradingDataType.TICKER.equals(trading_data_type):
                    data["tickers"] = self.market_service.get_tickers(
                        symbols=strategy.symbols
                    )

                elif TradingDataType.ORDER_BOOK.equals(trading_data_type):
                    data["order_books"] = self.market_service.get_order_books(
                        symbols=strategy.symbols
                    )
                elif TradingDataType.OHLCV.equals(trading_data_type):

                    if strategy.trading_time_frame is None:
                        raise OperationalException(
                            "'trading_time_frame' attribute is not specified "
                            "for OHLCV data"
                        )

                    trading_time_frame_start_date = \
                        strategy.trading_time_frame_start_date

                    if strategy.trading_time_frame_start_date is not None:

                        if isinstance(
                            strategy.trading_time_frame_start_date, str
                        ):
                            trading_time_frame_start_date = \
                                datetime.strptime(
                                    strategy.trading_time_frame_start_date,
                                    DATETIME_FORMAT
                                )
                        elif not isinstance(
                            trading_time_frame_start_date, datetime
                        ):
                            raise OperationalException(
                                "Invalid type for 'trading_time_"
                                "frame_start_date' attribute"
                            )
                    else:
                        trading_time_frame = TradingTimeFrame\
                            .from_value(strategy.trading_time_frame)
                        trading_time_frame_start_date = \
                            datetime.utcnow() - timedelta(
                                minutes=trading_time_frame.minutes
                            )

                    data["ohlcvs"] = self.market_service.get_ohclvs(
                        strategy.symbols,
                        time_frame=TradingTimeFrame
                        .from_value(strategy.trading_time_frame),
                        from_timestamp=trading_time_frame_start_date
                    )

        return data

