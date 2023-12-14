from investing_algorithm_framework.domain import PortfolioConfiguration
from .portfolio_service import PortfolioService


class BacktestPortfolioService(PortfolioService):
    """
    BacktestPortfolioService is a subclass of PortfolioService.
    It is used to create a portfolio for backtesting. This class does
    not check if the initial balance is present on the exchange or broker.
    """
    def create_portfolio_from_configuration(
        self, portfolio_configuration: PortfolioConfiguration
    ):
        data = {
            "identifier": portfolio_configuration.identifier,
            "market": portfolio_configuration.market,
            "trading_symbol": portfolio_configuration.trading_symbol,
            "unallocated": portfolio_configuration.initial_balance,
        }
        return self.create(data)
