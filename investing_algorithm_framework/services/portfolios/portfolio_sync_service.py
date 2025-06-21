import logging

from investing_algorithm_framework.domain import OperationalException, \
    AbstractPortfolioSyncService, ENVIRONMENT, Environment
from investing_algorithm_framework.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class PortfolioSyncService(AbstractPortfolioSyncService):
    """
    Service to sync the portfolio with the exchange.

    This service will sync the portfolio with the exchange

    Attributes:
        trade_service: TradeService object
        configuration_service: ConfigurationService object
        order_service: OrderService object
        position_repository: PositionRepository object
        portfolio_repository: PortfolioRepository object
        market_credential_service: MarketCredentialService object
        market_service: MarketService object
        portfolio_configuration_service: PortfolioConfigurationService object
        portfolio_provider_lookup: PortfolioProviderLookup object
    """

    def __init__(
        self,
        trade_service: TradeService,
        configuration_service,
        order_service,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
        market_credential_service,
        market_service,
        portfolio_provider_lookup
    ):
        self.trade_service = trade_service
        self.configuration_service = configuration_service
        self.order_service = order_service
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.market_credential_service = market_credential_service
        self.market_service = market_service
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_provider_lookup = portfolio_provider_lookup

    def sync_unallocated(self, portfolio):
        """
        Method to sync the unallocated balance of the portfolio with the
        available balance on the exchange. This method will retrieve the
        available balance of the portfolio from the exchange and update the
        unallocated balance of the portfolio accordingly.

        If the portfolio already exists (exists in the database),
        then a check is done if the exchange has the available
        balance of the portfolio unallocated balance. If the exchange
        does not have the available balance of the portfolio,
        an OperationalException will be raised.

        If the portfolio does not exist, the portfolio will be created with
        the unallocated balance of the portfolio set to the available
        balance on the exchange. If also a initial balance is set in
        the portfolio configuration, the unallocated balance will be set
        to the initial balance (given the balance is available on
        the exchange). If the initial balance is not set, the
        unallocated balance will be set to the available balance
        on the exchange.

        Args:
            portfolio: Portfolio object

        Returns:
            Portfolio object
        """
        market_credential = self.market_credential_service.get(
            portfolio.market
        )

        if market_credential is None:
            raise OperationalException(
                f"No market credential found for market "
                f"{portfolio.market}. Cannot sync unallocated amount."
            )

        portfolio_provider = self.portfolio_provider_lookup\
            .get_portfolio_provider(portfolio.market)
        position = portfolio_provider.get_position(
            portfolio, portfolio.trading_symbol, market_credential
        )

        if not portfolio.initialized:
            # Check if the portfolio has an initial balance set
            if portfolio.initial_balance is not None:
                available = position.amount

                if portfolio.initial_balance > available:
                    raise OperationalException(
                        "The initial balance of the " +
                        "portfolio configuration " +
                        f"({portfolio.initial_balance} "
                        f"{portfolio.trading_symbol}) is more " +
                        "than the available balance on the exchange. " +
                        "Please make sure that the initial balance of " +
                        "the portfolio configuration is less " +
                        "than the available balance on the " +
                        f"exchange {available} {portfolio.trading_symbol}."
                    )
                else:
                    unallocated = portfolio.initial_balance
            else:
                # If the portfolio does not have an initial balance
                # set, get the available balance on the exchange
                if position is None:
                    raise OperationalException(
                        f"There is no available balance on the exchange for "
                        f"{portfolio.trading_symbol.upper()} on market "
                        f"{portfolio.market}. Please make sure that you have "
                        f"an available balance on the exchange for "
                        f"{portfolio.trading_symbol.upper()} on market "
                        f"{portfolio.market}."
                    )
                else:
                    unallocated = position.amount

            update_data = {
                "unallocated": unallocated,
                "net_size": unallocated,
                "initialized": True
            }
            portfolio = self.portfolio_repository.update(
                portfolio.id, update_data
            )

            # Update also a trading symbol position
            trading_symbol_position = self.position_repository.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio_id": portfolio.id
                }
            )
            self.position_repository.update(
                trading_symbol_position.id, {"amount": unallocated}
            )

        else:
            # Check if the portfolio unallocated balance is
            # available on the exchange
            if portfolio.unallocated > 0:
                if position is None or portfolio.unallocated > position.amount:
                    raise OperationalException(
                        f"Out of sync: the unallocated balance"
                        " of the exiting portfolio is more than the available"
                        " balance on the exchange. Please make sure"
                        " that you have at least "
                        f"{portfolio.unallocated}"
                        f" {portfolio.trading_symbol.upper()} available"
                        " on the exchange."
                    )

        return portfolio

    def sync_orders(self, portfolio):
        """
        Function to sync all local orders with the orders on the exchange.
        This method will go over all local open orders and check if they are
        changed on the exchange. If they are, the local order will be
        updated to match the status on the exchange.

        Args:
            portfolio: Portfolio object

        Returns:
            None
        """

        config = self.configuration_service.get_config()

        if ENVIRONMENT in config \
                and Environment.BACKTEST.equals(config[ENVIRONMENT]):
            return

        self.order_service.check_pending_orders(portfolio)
