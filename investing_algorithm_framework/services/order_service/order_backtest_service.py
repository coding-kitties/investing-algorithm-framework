import logging

from investing_algorithm_framework.domain import BACKTESTING_INDEX_DATETIME, \
    OrderStatus, BACKTESTING_PENDING_ORDER_CHECK_INTERVAL, OperationalException
from investing_algorithm_framework.services.market_data_source_service \
    import BacktestMarketDataSourceService
from .order_service import OrderService

logger = logging.getLogger("investing_algorithm_framework")


class OrderBacktestService(OrderService):

    def __init__(
        self,
        order_repository,
        order_fee_repository,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        configuration_service,
        market_data_source_service: BacktestMarketDataSourceService,
    ):
        super(OrderService, self).__init__(order_repository)
        self.order_repository = order_repository
        self.order_fee_repository = order_fee_repository
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.configuration_service = configuration_service
        self._market_data_source_service: BacktestMarketDataSourceService = \
            market_data_source_service

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

    def check_pending_orders(self):
        pending_orders = self.get_all({"status": OrderStatus.OPEN.value})
        logger.info(f"Checking {len(pending_orders)} open orders")
        config = self.configuration_service.get_config()

        for order in pending_orders:
            symbol = f"{order.target_symbol.upper()}" \
                     f"/{order.trading_symbol.upper()}"
            position = self.position_repository.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)

            if not self._market_data_source_service\
                    .is_ohlcv_data_source_present(
                        symbol=symbol,
                        market=portfolio.market,
                        time_frame=self.configuration_service
                        .config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]
                    ):
                raise OperationalException(
                    f"OHLCV data source not found for {symbol} "
                    f"and market {portfolio.market} for order check "
                    f"time frame "
                    f"{config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]}. "
                    f"Cannot check pending orders for symbol {symbol} "
                    f"with market {portfolio.market}. Please add a ohlcv data"
                    f"source for {symbol} and market {portfolio.market} with "
                    f"time frame {config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]} "
                )

            market_data = self._market_data_source_service.get_ohlcv(
                symbol=symbol,
                market=portfolio.market,
                to_timestamp=self.configuration_service.config.get(
                    BACKTESTING_INDEX_DATETIME
                ),
                from_timestamp=order.get_created_at(),
                time_frame=self.configuration_service
                .config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]
            )
            data_slice = [
                ohclv for ohclv in market_data
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
                break

    def cancel_order(self, order):
        self.check_pending_orders()
        order = self.order_repository.get(order.id)

        if order is not None:

            if OrderStatus.OPEN.equals(order.status):
                portfolio = self.portfolio_repository\
                    .find({"position": order.position_id})
                self.update(
                    order.id,
                    {
                        "status": OrderStatus.CANCELED.value,
                        "remaining": 0,
                        "updated_at": self.configuration_service
                        .config[BACKTESTING_INDEX_DATETIME]
                    }
                )

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
