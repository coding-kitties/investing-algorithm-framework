from investing_algorithm_framework.exchanges import BinanceExchangeClient


class BinancePortfolioManagerMixin(BinanceExchangeClient):

    def get_initial_unallocated_size(self):
        return self.get_balance(self.get_trading_currency())
