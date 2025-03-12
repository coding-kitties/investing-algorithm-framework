import logging
from datetime import datetime

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    OperationalException, MarketService, MarketCredentialService, Portfolio, \
    Environment, ENVIRONMENT
from investing_algorithm_framework.services.configuration_service import \
    ConfigurationService
from investing_algorithm_framework.services.repository_service \
    import RepositoryService

logger = logging.getLogger("investing_algorithm_framework")


class PortfolioService(RepositoryService):
    """
    Service to manage portfolios. This service will sync the portfolios with
    the exchange balances and orders. It will also create portfolios based on
    the portfolio configurations registered by the user
    """

    def __init__(
        self,
        configuration_service: ConfigurationService,
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        order_service,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        position_service
    ):
        self.configuration_service = configuration_service
        self.market_credential_service = market_credential_service
        self.market_service = market_service
        self.portfolio_configuration_service = portfolio_configuration_service
        self.order_service = order_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.position_service = position_service
        super(PortfolioService, self).__init__(portfolio_repository)

    def find(self, query_params):
        portfolio = self.repository.find(query_params)
        portfolio_configuration = self.portfolio_configuration_service\
            .get(portfolio.identifier)
        portfolio.configuration = portfolio_configuration
        return portfolio

    def get_all(self, query_params=None):
        selection = super().get_all(query_params)

        for portfolio in selection:
            portfolio_configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)
            portfolio.configuration = portfolio_configuration

        return selection

    def create(self, data):
        unallocated = data.get("unallocated", 0)
        market = data.get("market")

        # Check if the app is in backtest mode
        config = self.configuration_service.get_config()
        environment = config[ENVIRONMENT]

        if not Environment.BACKTEST.equals(environment):
            # Check if there is a market credential
            # for the portfolio configuration
            market_credential = self.market_credential_service.get(market)

            if market_credential is None:
                raise OperationalException(
                    f"No market credential found for market "
                    f"{market}. Cannot "
                    f"initialize portfolio configuration."
                )

        identifier = data.get("identifier")
        # Check if the portfolio already exists
        # If the portfolio already exists, return the portfolio after checking
        # the unallocated balance of the portfolio on the exchange
        if identifier is not None and self.repository.exists(
            {"identifier": identifier}
        ):
            portfolio = self.repository.find(
                {"identifier": identifier}
            )
            return portfolio

        portfolio = super(PortfolioService, self).create(data)
        self.position_service.create(
            {
                "symbol": portfolio.get_trading_symbol(),
                "amount": unallocated,
                "portfolio_id": portfolio.id,
                "cost": unallocated
            }
        )
        self.create_snapshot(portfolio.id, created_at=portfolio.created_at)
        return portfolio

    def create_snapshot(self, portfolio_id, created_at=None):

        if created_at is None:
            created_at = datetime.utcnow()

        portfolio = self.get(portfolio_id)
        pending_orders = self.order_service.get_all(
            {
                "order_side": OrderSide.BUY.value,
                "status": OrderStatus.OPEN.value,
                "portfolio_id": portfolio.id
            }
        )
        return self.portfolio_snapshot_service.create_snapshot(
            portfolio,
            pending_orders=pending_orders,
            created_at=created_at
        )

    def create_portfolio_from_configuration(
        self, portfolio_configuration, initial_amount=None
    ) -> Portfolio:
        """
        Method to create a portfolio based on a portfolio configuration.
        This method will create a portfolio based on the configuration
        provided. If the portfolio already exists, it will be returned.

        If the portfolio does not exist, it will be created.

        Args:
            portfolio_configuration (PortfolioConfiguration)
                Portfolio configuration to create the portfolio from
            initial_amount (Decimal): Initial balance for the portfolio

        Returns:
            Portfolio: Portfolio created from the configuration
        """
        logger.info("Creating portfolios")

        # Check if there is a market credential for the portfolio configuration
        market_credential = self.market_credential_service.get(
            portfolio_configuration.market
        )

        if market_credential is None:
            raise OperationalException(
                f"No market credential found for market "
                f"{portfolio_configuration.market}. Cannot "
                f"initialize portfolio configuration."
            )

        # Check if the portfolio already exists
        # If the portfolio already exists, return the portfolio after checking
        # the unallocated balance of the portfolio on the exchange
        if self.repository.exists(
            {"identifier": portfolio_configuration.identifier}
        ):
            portfolio = self.repository.find(
                {"identifier": portfolio_configuration.identifier}
            )
            return portfolio
        else:
            # Create a new portfolio
            portfolio = Portfolio.from_portfolio_configuration(
                portfolio_configuration
            )
            data = portfolio.to_dict()

            if initial_amount is not None:
                data["unallocated"] = initial_amount

            self.create(data)

        return portfolio
