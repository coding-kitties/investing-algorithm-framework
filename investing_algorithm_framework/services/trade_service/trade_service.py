import logging
from queue import PriorityQueue

from investing_algorithm_framework.domain import OrderStatus, \
    TradeStatus, Trade, OperationalException, MarketDataType
from investing_algorithm_framework.services.repository_service import \
    RepositoryService

logger = logging.getLogger(__name__)


class TradeService(RepositoryService):

    def __init__(
        self,
        trade_repository,
        position_repository,
        portfolio_repository,
        market_data_source_service,
        configuration_service
    ):
        super(TradeService, self).__init__(trade_repository)
        self.portfolio_repository = portfolio_repository
        self.market_data_source_service = market_data_source_service
        self.position_repository = position_repository
        self.configuration_service = configuration_service

    def create_trade_from_buy_order(self, buy_order) -> Trade:
        """
        Function to create a trade from a buy order. If the given buy
        order has its status set to CANCELED, EXPIRED, or REJECTED,
        the trade object will not be created. If the given buy
        order has its status set to CLOSED or OPEN, the trade object
        will be created. The amount will be set to the filled amount.

        Args:
            buy_order: Order object representing the buy order

        Returns:
            Trade object
        """
        status = buy_order.get_status()

        if status in \
                [
                    OrderStatus.CANCELED.value,
                    OrderStatus.EXPIRED.value,
                    OrderStatus.REJECTED.value
                ]:
            return None

        data = {
            "buy_order": buy_order,
            "target_symbol": buy_order.target_symbol,
            "trading_symbol": buy_order.trading_symbol,
            "amount": buy_order.filled,
            "remaining": buy_order.filled,
            "opened_at": buy_order.created_at,
            "cost": buy_order.filled * buy_order.price
        }

        if buy_order.filled > 0:
            data["status"] = TradeStatus.OPEN.value
            data["cost"] = buy_order.filled * buy_order.price

        return self.create(data)

    def update_trade_with_buy_order(
        self, filled_difference, buy_order
    ) -> Trade:
        """
        Function to update a trade from a buy order. This function
        checks if a trade exists for the buy order. If the given buy
        order has its status set to CANCLED, EXPIRED, or REJECTED, the
        trade will object will be removed. If the given buy order has
        its status set to CLOSED or OPEN, the amount and
        remaining of the trade object will be updated.

        Args:
            filled_difference: float representing the difference between the
                filled amount of the buy order and the filled amount
                of the trade
            buy_order: Order object representing the buy order

        Returns:
            Trade object
        """

        trade = self.find({"buy_order": buy_order.id})

        if trade is None:
            raise OperationalException(
                "Trade does not exist for buy order."
            )

        status = buy_order.get_status()

        if status in \
                [
                    OrderStatus.CANCELED.value,
                    OrderStatus.EXPIRED.value,
                    OrderStatus.REJECTED.value
                ]:
            return self.delete(trade.id)

        trade = self.find({"order_id": buy_order.id})
        updated_data = {
            "amount": trade.amount + filled_difference,
            "remaining": trade.remaining + filled_difference,
            "cost": trade.cost + filled_difference * buy_order.price
        }

        if filled_difference > 0:
            updated_data["status"] = TradeStatus.OPEN.value

        trade = self.update(trade.id, updated_data)
        return trade

    def update_trade_with_sell_order_filled(
        self, filled_amount, sell_order
    ) -> Trade:
        """
        Function to update a trade from a sell order that has been filled.
        This function checks if a trade exists for the buy order.
        If the given buy order has its status set to
        CANCLED, EXPIRED, or REJECTED, the
        trade will object will be removed. If the given buy order
        has its status set to CLOSED or OPEN, the amount and
        remaining of the trade object will be updated.

        Args:
            sell_order: Order object representing the sell order that has
                been filled.
            filled_amount: float representing the filled amount of the sell
                order

        Returns:
            Trade object
        """

        # Only update the trade if the sell order has been filled
        if sell_order.get_status() != OrderStatus.CLOSED.value:
            return None

        position = self.position_repository.find({
            "order_id": sell_order.id
        })
        portfolio_id = position.portfolio_id
        matching_trades = self.get_all({
            "status": TradeStatus.OPEN.value,
            "target_symbol": sell_order.target_symbol,
            "portfolio_id": portfolio_id
        })
        target_symbol = sell_order.target_symbol
        price = sell_order.price
        updated_at = sell_order.updated_at
        amount_to_close = filled_amount
        order_queue = PriorityQueue()
        total_net_gain = 0
        total_cost = 0
        total_remaining = 0

        for trade in matching_trades:
            if trade.remaining > 0:
                total_remaining += trade.remaining
                order_queue.put(trade)

        if total_remaining < amount_to_close:
            raise OperationalException(
                "Not enough amount to close in trades."
            )

        while amount_to_close > 0 and not order_queue.empty():
            trade = order_queue.get()
            available_to_close = trade.remaining

            if amount_to_close >= available_to_close:
                cost = trade.buy_order.price * available_to_close
                net_gain = (price * available_to_close) - cost
                amount_to_close = amount_to_close - available_to_close
                self.update(
                    trade.id, {
                        "remaining": 0,
                        "closed_at": updated_at,
                        "net_gain": trade.net_gain + net_gain,
                        "status": TradeStatus.CLOSED.value
                    }
                )
                self.repository.add_order_to_trade(trade, sell_order)
            else:
                to_be_closed = amount_to_close
                cost = trade.buy_order.price * to_be_closed
                net_gain = (price * to_be_closed) - cost
                self.update(
                    trade.id, {
                        "remaining": trade.remaining - to_be_closed,
                        "net_gain": trade.net_gain + net_gain,
                        "orders": trade.orders.append(sell_order)
                    }
                )
                self.repository.add_order_to_trade(trade, sell_order)
                amount_to_close = 0

            total_net_gain += net_gain
            total_cost += cost

        portfolio = self.portfolio_repository.get(portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "total_net_gain": portfolio.total_net_gain + total_net_gain,
                "cost": portfolio.total_cost - total_cost
            }
        )
        position = self.position_repository.find(
            {
                "portfolio": portfolio.id,
                "symbol": target_symbol
            }
        )
        self.position_repository.update(
            position.id,
            {
                "cost": position.cost - total_cost,
            }
        )

    def update_trades_with_market_data(self, market_data):
        open_trades = self.get_all({"status": TradeStatus.OPEN.value})
        meta_data = market_data["metadata"]

        for open_trade in open_trades:
            ohlcv_meta_data = meta_data[MarketDataType.OHLCV]

            if open_trade.symbol not in ohlcv_meta_data:
                continue

            timeframes = ohlcv_meta_data[open_trade.symbol].keys()
            sorted_timeframes = sorted(timeframes)
            most_granular_interval = sorted_timeframes[0]
            identifier = (
                ohlcv_meta_data[open_trade.symbol][most_granular_interval]
            )
            data = market_data[identifier]

            # Get last row of data
            last_row = data.tail(1)
            update_data = {
                "last_reported_price": last_row["Close"][0],
                "updated_at": last_row["Datetime"][0]
            }
            price = last_row["Close"][0]

            if open_trade.trailing_stop_loss_percentage is not None:

                if open_trade.high_water_mark is None or \
                        open_trade.high_water_mark < price:
                    update_data["high_water_mark"] = price

            self.update(open_trade.id, update_data)

    def add_stop_loss(self, trade, percentage):
        """
        Function to add a stop loss to a trade. The stop loss is
        represented as a percentage of the open price.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at

        Returns:
            None
        """
        trade = self.get(trade.id)
        updated_data = {
            "stop_loss_percentage": percentage
        }
        self.update(trade.id, updated_data)

    def add_trailing_stop_loss(self, trade, percentage):
        """
        Function to add a trailing stop loss to a trade. The trailing stop loss
        is represented as a percentage of the open price.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the trailing stop loss should be set at

        Returns:
            None
        """
        trade = self.get(trade.id)
        updated_data = {
            "trailing_stop_loss_percentage": percentage
        }
        self.update(trade.id, updated_data)

    def get_triggered_stop_losses(self):
        """
        Function to check if any trades have hit their stop loss. If a trade
        has hit its stop loss, the trade is added to a list of
        triggered trades. This list is then returned.

        Returns:
            List of Trade objects
        """
        triggered_trades = []
        query = {
            "status": TradeStatus.OPEN.value,
            "stop_loss_percentage_not_none": True
        }
        open_trades = self.get_all(query)

        for open_trade in open_trades:

            if open_trade.is_stop_loss_triggered():
                triggered_trades.append(open_trade)

        return triggered_trades

    def get_triggered_trailing_stop_losses(self):
        """
        Function to check if any trades have hit their stop loss. If a trade
        has hit its stop loss, the trade is added to a list of
        triggered trades. This list is then returned.

        Returns:
            List of Trade objects
        """
        triggered_trades = []
        query = {
            "status": TradeStatus.OPEN.value,
            "trailing_stop_loss_percentage_not_none": True
        }
        open_trades = self.get_all(query)

        for open_trade in open_trades:

            if open_trade.is_trailing_stop_loss_triggered():
                triggered_trades.append(open_trade)

        return triggered_trades
