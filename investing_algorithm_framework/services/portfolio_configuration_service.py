from investing_algorithm_framework.domain import ApiException


class PortfolioConfigurationService:

    def __init__(
            self, portfolio_repository, position_repository, market_service
    ):
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.market_service = market_service
        self.portfolio_configurations = []

    def add(self, portfolio_configuration):
        self.portfolio_configurations.append(portfolio_configuration)

    def get(self, identifier):
        portfolio_configuration = next(
            (portfolio_configuration for portfolio_configuration in
                self.portfolio_configurations if
                portfolio_configuration.identifier == identifier.lower()),
            None
        )

        if portfolio_configuration is None:
            raise ApiException('Portfolio configuration not found', 404)

        return portfolio_configuration

    def find(self, query_params):
        market = query_params.get("market", None)
        identifier = query_params.get("market", None)

        if market is not None:
            return next(
                (portfolio_configuration for portfolio_configuration in
                 self.portfolio_configurations if
                 portfolio_configuration.market == market.lower()),
                None
            )
        elif identifier is not None:
            return next(
                (portfolio_configuration for portfolio_configuration in
                 self.portfolio_configurations if
                 portfolio_configuration.identifier == identifier.lower()),
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
