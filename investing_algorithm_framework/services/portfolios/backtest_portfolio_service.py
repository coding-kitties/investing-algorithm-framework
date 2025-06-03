from datetime import datetime
from investing_algorithm_framework.domain import PortfolioConfiguration, \
    OperationalException
from .portfolio_service import PortfolioService


class BacktestPortfolioService(PortfolioService):
    """
    BacktestPortfolioService is a subclass of PortfolioService.
    It is used to create a portfolio for backtesting. This class does
    not check if the initial balance is present on the exchange or broker.
    """
    def create_portfolio_from_configuration(
        self,
        portfolio_configuration: PortfolioConfiguration,
        initial_amount=None,
        created_at: datetime = None
    ):
        """
        Wil create a portfolio from a portfolio configuration for backtesting.

        Args:
            portfolio_configuration (PortfolioConfiguration):
                Portfolio configuration to create the portfolio from
            initial_amount (Decimal): Initial balance for the portfolio
            created_at (datetime): The date and time when the portfolio
                is created. If not provided, the current date and time
                will be used.

        Returns:
            Portfolio: The created portfolio
        """
        amount = portfolio_configuration.initial_balance

        if initial_amount is not None:
            amount = initial_amount

        if amount is None:
            raise OperationalException(
                "Initial amount is required as a parameter or the " +
                "'initial_balance' attribute needs to be set on the "
                "portfolio configuration before running the backtest."
            )

        data = {
            "identifier": portfolio_configuration.identifier,
            "market": portfolio_configuration.market,
            "trading_symbol": portfolio_configuration.trading_symbol,
            "unallocated": amount,
            "initialized": True,
            "created_at": created_at
        }
        return self.create(data)
