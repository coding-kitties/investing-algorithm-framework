import logging

from investing_algorithm_framework.domain import ApiException

logger = logging.getLogger(__name__)


class PortfolioConfigurationService:
    """
    Service to manage portfolio configurations. This service will
    manage the portfolio configurations that the user has
    registered in the app.
    """

    def __init__(self, portfolio_repository, position_repository):
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.portfolio_configurations = []

    def add(self, portfolio_configuration):
        self.portfolio_configurations.append(portfolio_configuration)

    def get(self, identifier):
        portfolio_configuration = next(
            (
                portfolio_configuration for portfolio_configuration in
                self.portfolio_configurations
                if portfolio_configuration.identifier.upper() ==
                identifier.upper()),
            None
        )

        # if portfolio_configuration is None:
        #     raise ApiException(
        #         f'Portfolio configuration not '
        #         f'found for {identifier}'
        #         " Please make sure that you have registered a portfolio "
        #         "configuration for the portfolio you are trying to use",
        #         404
        #     )

        return portfolio_configuration

    def find(self, query_params):
        market = query_params.get("market", None)
        identifier = query_params.get("market", None)

        if market is not None:
            return next(
                (portfolio_configuration for portfolio_configuration in
                 self.portfolio_configurations if
                 portfolio_configuration.market.upper() == market.upper()),
                None
            )
        elif identifier is not None:
            return next(
                (portfolio_configuration for portfolio_configuration in
                    self.portfolio_configurations if
                    portfolio_configuration.identifier.upper()
                    == identifier.upper()),
                None
            )
        elif market is None and identifier is None:
            return self.portfolio_configurations[0]
        else:
            raise ApiException('Portfolio configuration not found', 404)

    def get_all(self):
        return self.portfolio_configurations

    def count(self):
        return len(self.portfolio_configurations)

    def clear(self):
        self.portfolio_configurations = []
