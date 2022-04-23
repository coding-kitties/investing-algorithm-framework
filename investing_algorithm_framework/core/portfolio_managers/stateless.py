from datetime import datetime
from typing import List

from investing_algorithm_framework.core.models import Order, Position
from investing_algorithm_framework.core.portfolio_managers.portfolio_manager\
    import PortfolioManager


class StatelessPortfolioManager(PortfolioManager):

    def __init__(self, identifier, portfolio):
        self.identifier = identifier
        self.trading_symbol = portfolio.get_trading_symbol()
        super(StatelessPortfolioManager, self).__init__()
        self.portfolio = portfolio

    @staticmethod
    def of_portfolio(portfolio):
        return StatelessPortfolioManager(
            identifier=portfolio.get_identifier(),
            portfolio=portfolio
        )

    def get_positions(self, algorithm_context=None, **kwargs) -> List[Position]:
        return self.portfolio.get_positions()

    def get_orders(self, symbol, since: datetime = None,
                   algorithm_context=None, **kwargs) -> List[Order]:
        return self.portfolio.get_orders()