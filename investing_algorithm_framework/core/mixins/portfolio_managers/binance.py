from investing_algorithm_framework.core.market_services import \
    BinanceMarketService


class BinancePortfolioManagerMixin(BinanceMarketService):

    def get_initial_unallocated_size(self):
        return self.get_balance(self.get_trading_symbol())
