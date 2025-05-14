import logging

import polars as pl

from investing_algorithm_framework.domain import BACKTESTING_INDEX_DATETIME, \
    OrderStatus, OrderSide, Order, MarketDataType
from investing_algorithm_framework.services.market_data_source_service \
    import BacktestMarketDataSourceService
from .order_service import OrderService

logger = logging.getLogger("investing_algorithm_framework")


class OrderBacktestService(OrderService):

    def __init__(
        self,
        order_repository,
        trade_service,
        position_service,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        configuration_service,
        market_data_source_service: BacktestMarketDataSourceService,
    ):
        super(OrderService, self).__init__(order_repository)
        self.trade_service = trade_service
        self.order_repository = order_repository
        self.position_service = position_service
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.configuration_service = configuration_service
        self._market_data_source_service: BacktestMarketDataSourceService = \
            market_data_source_service

    def create(self, data, execute=True, validate=True, sync=True) -> Order:
        """
        Override the create method to set the created_at and
        updated_at attributes to the current backtest time.

        Args:
            data (dict): Dictionary containing the order data
            execute (bool): Flag to execute the order
            validate (bool): Flag to validate the order
            sync (bool): Flag to sync the order

        Returns:
            Order: Created order object
        """
        config = self.configuration_service.get_config()

        # Make sure the created_at is set to the current backtest time
        data["created_at"] = config[BACKTESTING_INDEX_DATETIME]
        data["updated_at"] = config[BACKTESTING_INDEX_DATETIME]
        # Call super to have standard behavior
        return super(OrderBacktestService, self)\
            .create(data, execute, validate, sync)

    def execute_order(self, order, portfolio):
        order.status = OrderStatus.OPEN.value
        order.remaining = order.get_amount()
        order.filled = 0
        order.updated_at = self.configuration_service.config[
            BACKTESTING_INDEX_DATETIME
        ]
        return order

    def check_pending_orders(self, market_data):
        """
        Function to check if any pending orders have executed. It querys the
        open orders and checks if the order has executed based on the OHLCV
        data. If the order has executed, the order status is set to CLOSED
        and the filled amount is set to the order amount.

        Args:
            market_data (dict): Dictionary containing the market data

        Returns:
            None
        """
        pending_orders = self.get_all({"status": OrderStatus.OPEN.value})
        meta_data = market_data["metadata"]

        for order in pending_orders:
            ohlcv_meta_data = meta_data[MarketDataType.OHLCV]

            if order.get_symbol() not in ohlcv_meta_data:
                continue

            timeframes = ohlcv_meta_data[order.get_symbol()].keys()
            sorted_timeframes = sorted(timeframes)
            most_granular_interval = sorted_timeframes[0]
            identifier = (
                ohlcv_meta_data[order.get_symbol()][most_granular_interval]
            )
            data = market_data[identifier]

            if self.has_executed(order, data):
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
        column_type = ohlcv_data_frame['Datetime'].dtype

        if isinstance(column_type, pl.Datetime):
            ohlcv_data_after_order = ohlcv_data_frame.filter(
                pl.col('Datetime') >= created_at
            )
        else:
            ohlcv_data_after_order = ohlcv_data_frame.filter(
                pl.col('Datetime') >= created_at.strftime(
                    self.configuration_service.config["DATETIME_FORMAT"]
                )
            )

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
