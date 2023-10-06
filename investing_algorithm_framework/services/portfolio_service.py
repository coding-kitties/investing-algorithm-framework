import logging
from investing_algorithm_framework.services.repository_service \
    import RepositoryService


logger = logging.getLogger("investing_algorithm_framework")


class PortfolioService(RepositoryService):

    def __init__(
        self,
        market_service,
        position_repository,
        order_service,
        portfolio_repository,
        portfolio_configuration_service,
    ):
        self.market_service = market_service
        self.position_repository = position_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.order_service = order_service
        super(PortfolioService, self).__init__(portfolio_repository)

    def find(self, query_params):
        portfolio = self.repository.find(query_params)
        portfolio_configuration = self.portfolio_configuration_service\
            .get(portfolio.identifier)
        portfolio.configuration = portfolio_configuration
        return portfolio

    def create(self, data):
        unallocated = data.get("unallocated", 0)
        del data["unallocated"]
        portfolio = super(PortfolioService, self).create(data)
        self.position_repository.create(
            {
                "symbol": portfolio.get_trading_symbol(),
                "amount": unallocated,
                "portfolio_id": portfolio.id
            }
        )

    def sync_portfolios(self):

        for portfolio in self.get_all():
            portfolio_configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)

            self.market_service.initialize(portfolio_configuration)
            balances = self.market_service.get_balance()

            for symbol in balances:
                logger.info(f"Syncing {symbol} balance")
                logger.info(f"Balance: {balances[symbol]}")

                if "free" in balances[symbol]:

                    if self.position_repository.exists(
                        {"portfolio_id": portfolio.id, "symbol": symbol}
                    ):
                        position = self.position_repository.find(
                            {
                                "portfolio_id": portfolio.id,
                                "symbol": symbol
                            }
                        )
                        self.position_repository.update(
                            position.id,
                            {"amount": balances[symbol]["free"]}
                        )
                    else:
                        self.position_repository.create(
                            {
                                "symbol": symbol,
                                "amount": balances[symbol]["free"],
                                "portfolio_id": portfolio.id
                            }
                        )

                    if symbol == portfolio.trading_symbol:
                        if portfolio.unallocated != balances[symbol]["free"]:
                            logger.info(
                                "Updating unallocated balance "
                                f"from {portfolio.unallocated} "
                                f"to {balances[symbol]['free']}"
                            )
                            difference = balances[symbol]["free"] \
                                         - portfolio.get_unallocated()
                            self.update(
                                portfolio.id,
                                {
                                    "unallocated": portfolio.get_unallocated() + difference,
                                    "net_size": portfolio.get_net_size() + difference
                                }
                            )


            for position in self.position_repository.get_all(
                {"portfolio_id": portfolio.id}
            ):
                if position.symbol == portfolio.trading_symbol:
                    continue

                logger.info(f"Syncing {position.symbol} orders")

                external_orders = self.market_service\
                    .get_orders(
                        f"{position.symbol}/{portfolio.trading_symbol}",
                        since=portfolio_configuration.track_from
                    )

                logger.info(
                    f"Found {len(external_orders)} external orders "
                    f"for position {position.symbol}"
                )

                for external_order in external_orders:

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
                            "Creating new order based on external order"
                        )
                        data = external_order.to_dict()
                        data["position_id"] = position.id
                        data["portfolio_id"] = portfolio.id
                        self.order_service.create(
                            data, execute=False, validate=False, sync=False
                        )
