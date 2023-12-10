from .portfolio_configuration import PortfolioConfiguration


class BacktestPortfolioConfiguration(PortfolioConfiguration):

    def __init__(
        self,
        market,
        trading_symbol,
        unallocated,
        identifier=None,
    ):
        super().__init__(
            market=market,
            trading_symbol=trading_symbol,
            api_key=None,
            secret_key=None,
            identifier=identifier,
            max_unallocated=unallocated,
            backtest=True
        )
