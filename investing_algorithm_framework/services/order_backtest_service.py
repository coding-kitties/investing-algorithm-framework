import logging

from investing_algorithm_framework.domain import BACKTESTING_INDEX_DATETIME, \
    OrderStatus
from .order_service import OrderService

logger = logging.getLogger("investing_algorithm_framework")


class OrderBacktestService(OrderService):

    def __init__(
        self,
        order_repository,
        order_fee_repository,
        market_service,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        configuration_service,
    ):
        super(OrderService, self).__init__(order_repository)
        self.order_repository = order_repository
        self.order_fee_repository = order_fee_repository
        self.market_service = market_service
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.configuration_service = configuration_service

    def execute_order(self, order_id, portfolio):
        order = self.get(order_id)
        order = self.update(
            order_id,
            {
                "status": OrderStatus.OPEN.value,
                "remaining": order.remaining,
                "updated_at": self.configuration_service
                .config[BACKTESTING_INDEX_DATETIME]
            }
        )
        return order

    def check_pending_orders(self, ohlcvs=None):
        pending_orders = self.get_all({"status": OrderStatus.OPEN.value})
        logger.info(f"Checking {len(pending_orders)} open orders")

        for order in pending_orders:
            symbol = f"{order.target_symbol.upper()}" \
                     f"/{order.trading_symbol.upper()}"

            if symbol in ohlcvs:
                data_slice = [
                    ohclv for ohclv in ohlcvs[symbol]
                    if ohclv[0] >= order.get_created_at()
                ]

                if self.has_executed(order, data_slice):
                    self.update(
                        order.id,
                        {
                            "status": OrderStatus.CLOSED.value,
                            "filled": order.get_amount(),
                            "remaining": 0,
                            "updated_at": self.configuration_service
                            .config[BACKTESTING_INDEX_DATETIME]
                        }
                    )

    def cancel_order(self, order_id):
        self.check_pending_orders(ohlcvs={})
        order = self.order_repository.get(order_id)

        if order is not None:

            if OrderStatus.OPEN.equals(order.status):
                portfolio = self.portfolio_repository\
                    .find({"position": order.position_id})
                portfolio_configuration = self.portfolio_configuration_service\
                    .get(portfolio.identifier)
                self.market_service.initialize(portfolio_configuration)
                self.market_service.cancel_order(order_id)

    def check_ohclv(self, order, ohclv):
        data = ohclv

        if len(data) == 0:
            return False

        lowest_price = None
        highest_price = None

        for ohclv in data:

            if lowest_price is None:
                lowest_price = ohclv[3]
            else:
                lowest_price = min(lowest_price, ohclv[3])

            if highest_price is None:
                highest_price = ohclv[2]
            else:
                highest_price = max(highest_price, ohclv[2])

        if highest_price >= order.get_price() >= lowest_price:
            return True

        return False

    def has_executed(self, order, ohclv):
        return self.check_ohclv(order, ohclv)

    def create_snapshot(self, portfolio_id, created_at=None):

        if created_at is None:
            created_at = self.configuration_service \
                .config[BACKTESTING_INDEX_DATETIME]

        super(OrderBacktestService, self)\
            .create_snapshot(portfolio_id, created_at=created_at)
