import logging

import pandas as pd

from investing_algorithm_framework.domain import BACKTESTING_INDEX_DATETIME, \
    OrderStatus, BACKTESTING_PENDING_ORDER_CHECK_INTERVAL, \
    OperationalException, OrderSide, Order
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

    def create(self, data, execute=True, validate=True, sync=True) -> Order:
        # Make sure the created_at is set to the current backtest time
        data["created_at"] = self.configuration_service\
            .config[BACKTESTING_INDEX_DATETIME]
        # Call super to have standard behavior
        return super(OrderBacktestService, self)\
            .create(data, execute, validate, sync)

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
                    f"time frame "
                    f"{config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]} "
                )

            df = self._market_data_source_service.get_ohlcv(
                symbol=symbol,
                market=portfolio.market,
                to_timestamp=self.configuration_service.config.get(
                    BACKTESTING_INDEX_DATETIME
                ),
                from_timestamp=order.get_created_at(),
                time_frame=self.configuration_service
                .config[BACKTESTING_PENDING_ORDER_CHECK_INTERVAL]
            )

            # Convert polaris df to pandas df
            df = df.to_pandas()

            # Convert the 'Datetime' column to pandas Timestamp
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            df.set_index("Datetime", inplace=True)

            if self.has_executed(order, df):
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
                self.update(
                    order.id,
                    {
                        "status": OrderStatus.CANCELED.value,
                        "remaining": 0,
                        "updated_at": self.configuration_service
                        .config[BACKTESTING_INDEX_DATETIME]
                    }
                )

    def has_executed(self, order, ohlcv_data_frame):
        """
        Check if the order has executed based on the OHLCV data.

        A buy order is executed if the low price drops below or equals the
        order price. Example: If the order price is 1000 and the low price
        drops below or equals 1000, the order is executed. This simulates the
        situation where a buyer is willing to pay a higher price than the
        the lowest price in the ohlcv data.

        A sell order is executed if the high price goes above or equals the
        order price. Example: If the order price is 1000 and the high price
        goes above or equals 1000, the order is executed. This simulates the
        situation where a seller is willing to accept a higher price for its
        sell order.

        :param order: Order object
        :param ohlcv_data_frame: OHLCV data frame
        :return: True if the order has executed, False otherwise
        """

        # Extract attributes from the order object
        created_at = order.get_created_at()
        order_side = order.get_order_side()
        order_price = order.get_price()

        # Convert 'created_at' to pandas Timestamp for easier comparison
        created_at = pd.Timestamp(created_at, tz='UTC')

        # Filter OHLCV data after the order creation time
        ohlcv_data_after_order = ohlcv_data_frame.loc[created_at:]

        # print(ohlcv_data_frame)
        # print(ohlcv_data_after_order)
        # Check if the order execution conditions are met
        if OrderSide.BUY.equals(order_side):
            # Check if the low price drops below or equals the order price
            if (ohlcv_data_after_order['Low'] <= order_price).any():
                return True
        elif OrderSide.SELL.equals(order_side):
            # Check if the high price goes above or equals the order price
            if (ohlcv_data_after_order['High'] >= order_price).any():
                return True

        # If conditions are not met, return False
        return False

    def create_snapshot(self, portfolio_id, created_at=None):

        if created_at is None:
            created_at = self.configuration_service \
                .config[BACKTESTING_INDEX_DATETIME]

        super(OrderBacktestService, self)\
            .create_snapshot(portfolio_id, created_at=created_at)
