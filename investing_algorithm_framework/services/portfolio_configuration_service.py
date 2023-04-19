class PortfolioConfigurationService:

    def __init__(self, portfolio_repository, position_repository, market_service):
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.market_service = market_service
        self.portfolio_configurations = []

    def add(self, portfolio_configuration):
        self.portfolio_configurations.append(portfolio_configuration)

    def get(self, identifier):
        return next(
            (portfolio_configuration for portfolio_configuration in
                self.portfolio_configurations if
                portfolio_configuration.market == identifier.lower()),
            None
        )

    def get_all(self):
        return self.portfolio_configurations

    def count(self):
        return len(self.portfolio_configurations)

    def clear(self):
        self.portfolio_configurations = []
