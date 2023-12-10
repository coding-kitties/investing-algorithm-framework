import logging
from datetime import datetime

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    OperationalException
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
        portfolio_snapshot_service
    ):
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

    def sync_portfolios(self):

        for portfolio in self.get_all():
            portfolio_configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)

            self.market_service.initialize(portfolio_configuration)
            balances = self.market_service.get_balance()

            for symbol in balances["free"]:
                balance = balances["free"][symbol]
                logger.info(f"Syncing {symbol} balance")

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
                        {"amount": balance}
                    )
                else:
                    self.position_repository.create(
                        {
                            "symbol": symbol,
                            "amount": balance,
                            "portfolio_id": portfolio.id
                        }
                    )

                if symbol == portfolio.trading_symbol:
                    if portfolio.unallocated != balance:
                        logger.info(
                            "Updating unallocated balance "
                            f"from {portfolio.unallocated} "
                            f"to {balance}"
                        )
                        difference = balance - portfolio.get_unallocated()
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
        logger.info("Creating portfolios")

        self.market_service.initialize(portfolio_configuration)

        if self.repository.exists(
            {"identifier": portfolio_configuration.identifier}
        ):
            return self.repository.find(
                {"identifier": portfolio_configuration.identifier}
            )

        balances = self.market_service.get_balance()

        if portfolio_configuration.trading_symbol.upper() not in balances:
            raise OperationalException(
                f"Trading symbol balance not available "
                f"in portfolio on market {portfolio_configuration.market}"
            )

        unallocated = float(
            balances[portfolio_configuration.trading_symbol.upper()]
            ["free"]
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
