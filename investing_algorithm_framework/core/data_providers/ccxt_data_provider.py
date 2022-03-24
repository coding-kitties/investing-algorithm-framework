from typing import List

from investing_algorithm_framework.core.data_providers.data_provider import \
    DataProvider
from investing_algorithm_framework.core.models.data_provider import \
    Ticker, OrderBook, OHLCV, TradingTimeUnit


class CCXTDataProvider(DataProvider):

    def __init__(self, market):
        super().__init__(market)
        self.market = self.market.lower()

    def provide_ticker(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> Ticker:
        market_service = algorithm_context.get_market_service(self.market)
        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
        data = market_service.get_ticker(symbol)

        return Ticker(
            symbol=f"{target_symbol.upper()}{trading_symbol.upper()}",
            price=data["ask"],
            ask_price=data["ask"],
            ask_volume=data["askVolume"],
            bid_price=data["bid"],
            bid_volume=data["bidVolume"],
            high_price=data["high"],
            low_price=data["low"]
        )

    def provide_order_book(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> OrderBook:
        market_service = algorithm_context.get_market_service(self.market)
        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
        data = market_service.get_order_book(symbol)
        return OrderBook(
            symbol=f"{target_symbol.upper()}{trading_symbol.upper()}",
            bids=data["bids"],
            asks=data["asks"]
        )

    def provide_ohlcv(
        self,
        target_symbol,
        trading_symbol,
        trading_time_unit: TradingTimeUnit,
        limit,
        algorithm_context,
        **kwargs
    ) -> OHLCV:
        market_service = algorithm_context.get_market_service(self.market)
        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
        since = trading_time_unit.create_time_frame(limit)
        return market_service.get_ohclv(
            symbol=symbol,
            time_unit=trading_time_unit.to_ccxt_string(),
            since=since
        )

    def provide_ohlcvs(
        self,
        target_symbols,
        trading_symbol,
        trading_time_unit: TradingTimeUnit,
        limit,
        algorithm_context
    ) -> List[OHLCV]:
        market_service = algorithm_context.get_market_service(self.market)
        symbols = []

        for target_symbol in target_symbols:
            symbols.append(f"{target_symbol.upper()}/{trading_symbol.upper()}")

        since = trading_time_unit.create_time_frame(limit)

        return market_service.get_ohclvs(
            symbols=symbols,
            time_unit=trading_time_unit.to_ccxt_string(),
            since=since
        )
