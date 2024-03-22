import logging
from datetime import datetime

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    OperationalException, MarketService, MarketCredentialService
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
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        position_repository,
        order_service,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
    ):
        self.market_credential_service = market_credential_service
        self.market_service = market_service
        self.position_repository = position_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.order_service = order_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        super(PortfolioService, self).__init__(portfolio_repository)

    def find(self, query_params):
        portfolio = self.repository.find(query_params)
        portfolio_configuration = self.portfolio_configuration_service\
            .get(portfolio.identifier)
        portfolio.configuration = portfolio_configuration
        return portfolio

    def create(self, data):
        unallocated = data.get("unallocated", 0)
        portfolio = super(PortfolioService, self).create(data)
        self.position_repository.create(
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

    def create_portfolio_from_configuration(self, portfolio_configuration):
        """
        Method to create a portfolio based on a portfolio configuration.
        This method will create a portfolio based on the configuration
        provided. If the portfolio already exists, it will be returned.

        If the portfolio does not exist, it will be created. If the
        portfolio does not exist, the unallocated balance of the portfolio
        will be checked. If the unallocated balance of the portfolio is less
        than the initial balance of the portfolio configuration, an
        OperationalException will be raised.
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
            self.check_portfolio_unallocated_availability(
                portfolio, portfolio_configuration
            )
            return portfolio

        # If the portfolio does not exist, create the portfolio
        # Get the unallocated balance of the portfolio from the exchange
        balances = self.market_service\
            .get_balance(market=portfolio_configuration.market)

        if portfolio_configuration.trading_symbol.upper() not in balances:
            raise OperationalException(
                f"Trading symbol balance not available "
                f"in portfolio on market {portfolio_configuration.market}"
            )

        unallocated = float(
            balances[portfolio_configuration.trading_symbol.upper()]
            ["free"]
        )

        # If the unallocated balance of the portfolio is less than the initial
        # balance of the portfolio configuration, raise an OperationalException
        if portfolio_configuration.initial_balance is not None and \
                unallocated < portfolio_configuration.initial_balance:
            raise OperationalException(
                f"Insufficient balance on market "
                f"{portfolio_configuration.market} "
                f"for trading symbol "
                f"{portfolio_configuration.trading_symbol}. "
                f"Portfolio configuration initial balance: "
                f"{portfolio_configuration.initial_balance} "
                f"Available balance: {unallocated}"
            )

        creation_data = {
            "unallocated": unallocated,
            "identifier": portfolio_configuration.identifier,
            "trading_symbol": portfolio_configuration.trading_symbol.upper(),
            "market": portfolio_configuration.market.upper(),
        }

        portfolio = self.repository.create(creation_data)
        self.position_repository.create(
            {
                "symbol": portfolio.get_trading_symbol(),
                "amount": unallocated,
                "portfolio_id": portfolio.id,
                "cost": unallocated
            }
        )
        self.create_snapshot(portfolio.id, created_at=portfolio.created_at)
        return portfolio

    def check_portfolio_unallocated_availability(
        self, portfolio, portfolio_configuration
    ):
        """
        Method to check if the unallocated balance of the portfolio
        matches the available balance on the exchange.

        if the unallocated balance of the portfolio does not match the
        available balance on the exchange, an OperationalException will be
        raised.
        """
        balances = self.market_service \
            .get_balance(market=portfolio_configuration.market)

        # Make sure that the trading symbol is available in the balances
        if portfolio_configuration.trading_symbol.upper() not in balances:
            raise OperationalException(
                f"Trading symbol balance not available "
                f"in portfolio on market {portfolio_configuration.market}"
            )

        # Get the unallocated balance of the portfolio
        unallocated = float(
            balances[portfolio_configuration.trading_symbol.upper()]
            ["free"]
        )

        # If the unallocated balance of the portfolio is less than the
        # available balance on the exchange, raise an OperationalException
        if unallocated < portfolio.unallocated:
            raise OperationalException(
                "There seems to be a mismatch between the portfolio of this "
                "algorithm and the portfolio on the exchange. "
                f"Please make sure that the available "
                f"{portfolio.trading_symbol} "
                f"of your portfolio on the market {portfolio.market} "
                "matches the portfolio of this algorithm."
                f"Current portfolio: {portfolio.unallocated} "
                f"{portfolio.trading_symbol}"
                f"Available on market: {unallocated} "
                f"{portfolio.trading_symbol}"
            )

    def sync_portfolio_orders(self, portfolio):
        """
        Function to sync all local orders with the orders on the exchange.
        This function will retrieve all orders from the exchange and
        update the portfolio balances and positions accordingly.

        First all orders are retrieved from the exchange and updated in the
        database. If the order does not exist in the database, it will be
        created and treated as a new order.

        When an order is closed on the exchange, the order will be updated
        in the database to closed. We will also then update the portfolio
        and position balances accordingly.

        If the order exists, we will check if the filled amount of the order
        has changed. If the filled amount has changed, we will update the
        order in the database and update the portfolio and position balances

        if the status of an existing order has changed, we will update the
        order in the database and update the portfolio and position balances

        During the syncing of the orders, new orders are not executed. They
        are only created in the database. This is to prevent the algorithm
        from executing orders that are already executed on the exchange.
        """

        portfolio_configuration = self.portfolio_configuration_service \
            .get(portfolio.identifier)

        # Get all available symbols for the market and check if
        # there are orders
        available_symbols = self.market_service.get_symbols(
            market=portfolio.market
        )

        for symbol in available_symbols:
            orders = self.market_service.get_orders(
                symbol=symbol,
                since=portfolio_configuration.track_from,
                market=portfolio.market
            )

            if orders is not None and len(orders) > 0:
                # Order the list of orders by created_at
                ordered_external_order_list = sorted(
                    orders, key=lambda x: x.created_at
                )

                for external_order in ordered_external_order_list:
                    if self.order_service.exists(
                        {"external_id": external_order.external_id}
                    ):
                        logger.info("Updating existing order")
                        order = self.order_service.find(
                            {"external_id": external_order.external_id}
                        )
                        self.order_service.update(
                            order.id, external_order.to_dict()
                        )
                    else:
                        logger.info(
                            "Creating new order, based on external order"
                        )
                        data = external_order.to_dict()
                        data["portfolio_id"] = portfolio.id
                        data.pop("trade_closed_at", None)
                        data.pop("trade_closed_price", None)
                        data.pop("trade_closed_amount", None)

                        # Create the new order
                        new_order_data = {
                            "portfolio_id": portfolio.id,
                            "target_symbol": external_order.target_symbol,
                            "trading_symbol": portfolio.trading_symbol,
                            "amount": external_order.amount,
                            "price": external_order.price,
                            "order_side": external_order.order_side,
                            "order_type": external_order.order_type,
                            "external_id": external_order.external_id,
                        }
                        new_order = self.order_service.create(
                            new_order_data, execute=False, validate=False,
                        )

                        # Update the order to its current status
                        self.order_service.update(
                            new_order.id, external_order.to_dict()
                        )
