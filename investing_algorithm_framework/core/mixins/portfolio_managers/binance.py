from investing_algorithm_framework.configuration.constants import BINANCE


class BinancePortfolioManagerMixin:

    def get_orders(self, algorithm_context):
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_balance(self.trading_symbol)

    def get_positions(self, algorithm_context):
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_balance()

    def get_price(self, target_symbol, trading_symbol, algorithm_context):
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_ticker(target_symbol, trading_symbol)
