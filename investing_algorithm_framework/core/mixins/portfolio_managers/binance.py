from investing_algorithm_framework.configuration.constants import BINANCE


class BinancePortfolioManagerMixin:

    def get_unallocated_synced(self, algorithm_context):
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_balance(self.trading_symbol)

    def get_positions_synced(self, algorithm_context):
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_balance()

