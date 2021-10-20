from investing_algorithm_framework.core.market_services import \
    BinanceMarketService
from investing_algorithm_framework.core.models.data_provider import Ticker, \
    OrderBook
from investing_algorithm_framework.configuration.constants import BINANCE


class BinanceDataProviderMixin(BinanceMarketService):
    identifier = BINANCE

    def provide_ticker(
            self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> Ticker:
        market_service = algorithm_context.get_market_service(BINANCE)
        data = market_service.get_ticker(target_symbol, trading_symbol)

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
        market_service = algorithm_context.get_market_service(BINANCE)
        data = market_service.get_order_book(target_symbol, trading_symbol)
        return OrderBook(
            symbol=f"{target_symbol.upper()}{trading_symbol.upper()}",
            bids=data["bids"],
            asks=data["asks"]
        )
