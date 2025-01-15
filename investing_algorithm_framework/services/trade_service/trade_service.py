import logging
from queue import PriorityQueue
from typing import List

from investing_algorithm_framework.domain import OrderStatus, OrderSide, \
    Trade, PeekableQueue, OrderType, TradeStatus, \
    OperationalException, Order, RoundingService
from investing_algorithm_framework.services.market_data_source_service import \
    MarketDataSourceService
from investing_algorithm_framework.services.position_service import \
    PositionService

logger = logging.getLogger(__name__)


class TradeService:
    """
    Service for managing trades
    """

    def __init__(
        self,
        portfolio_repository,
        order_service,
        position_service,
        market_data_source_service
    ):
        self.portfolio_repository = portfolio_repository
        self.order_service = order_service
        self.market_data_source_service: MarketDataSourceService = \
            market_data_source_service
        self.position_service: PositionService = position_service

    def get_open_trades(self, target_symbol=None, market=None) -> List[Trade]:
        """
        Get open trades method

        Args:
            target_symbol: str representing the target symbol
            market: str representing the market

        Returns:
            list of Trade objects
        """

        portfolios = self.portfolio_repository.get_all()
        trades = []

        for portfolio in portfolios:

            if target_symbol is not None:
                buy_orders = self.order_service.get_all({
                    "status": OrderStatus.CLOSED.value,
                    "order_side": OrderSide.BUY.value,
                    "portfolio_id": portfolio.id,
                    "target_symbol": target_symbol
                })
                sell_orders = self.order_service.get_all({
                    "status": OrderStatus.OPEN.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio.id,
                    "target_symbol": target_symbol
                })
            else:
                buy_orders = self.order_service.get_all({
                    "status": OrderStatus.CLOSED.value,
                    "order_side": OrderSide.BUY.value,
                    "portfolio_id": portfolio.id
                })
                sell_orders = self.order_service.get_all({
                    "status": OrderStatus.OPEN.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio.id
                })

            buy_orders = [
                buy_order for buy_order in buy_orders
                if buy_order.get_trade_closed_at() is None
            ]
            sell_amount = sum([order.amount for order in sell_orders])

            # Subtract the amount of the open sell orders
            # from the amount of the buy orders
            buy_orders_queue = PeekableQueue()

            for buy_order in buy_orders:
                buy_orders_queue.enqueue(buy_order)

            while sell_amount > 0 and not buy_orders_queue.is_empty():
                first_buy_order = buy_orders_queue.peek()
                available = first_buy_order.get_filled() \
                    - first_buy_order.get_trade_closed_amount()

                if available > sell_amount:
                    remaining = available - sell_amount
                    sell_amount = 0
                    first_buy_order.set_filled(remaining)
                else:
                    sell_amount = sell_amount - available
                    buy_orders_queue.dequeue()

            for buy_order in buy_orders_queue:
                symbol = buy_order.get_symbol()
                current_price = buy_order.get_price()

                try:
                    ticker = self.market_data_source_service.get_ticker(
                        symbol=symbol, market=market
                    )
                    current_price = ticker["bid"]
                except Exception as e:
                    logger.error(e)

                amount = buy_order.get_filled()
                closed_amount = buy_order.get_trade_closed_amount()

                if closed_amount is not None:
                    amount = amount - closed_amount

                trades.append(
                    Trade(
                        buy_order_id=buy_order.id,
                        target_symbol=buy_order.get_target_symbol(),
                        trading_symbol=buy_order.get_trading_symbol(),
                        amount=amount,
                        open_price=buy_order.get_price(),
                        opened_at=buy_order.get_created_at(),
                        current_price=current_price
                    )
                )

        return trades

    def get_trades(self, market=None) -> List[Trade]:
        """
        Get trades method

        Args:
            market: str representing the market
            portfolio_id: str representing the portfolio id

        Returns:
            list of Trade objects
        """

        portfolios = self.portfolio_repository.get_all()
        trades = []

        for portfolio in portfolios:
            buy_orders = self.order_service.get_all({
                "status": OrderStatus.CLOSED.value,
                "order_side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id
            })

            for buy_order in buy_orders:
                symbol = buy_order.get_symbol()
                current_price = buy_order.get_price()
                try:
                    ticker = self.market_data_source_service.get_ticker(
                        symbol=symbol, market=market
                    )
                    current_price = ticker["bid"]
                except Exception as e:
                    logger.error(e)

                trades.append(
                    Trade(
                        buy_order_id=buy_order.id,
                        target_symbol=buy_order.get_target_symbol(),
                        trading_symbol=buy_order.get_trading_symbol(),
                        amount=buy_order.get_amount(),
                        open_price=buy_order.get_price(),
                        closed_price=buy_order.get_trade_closed_price(),
                        closed_at=buy_order.get_trade_closed_at(),
                        opened_at=buy_order.get_created_at(),
                        current_price=current_price
                    )
                )

        return trades

    def get_closed_trades(self, portfolio_id=None) -> List[Trade]:
        """
        Get closed trades method

        :param portfolio_id: str representing the portfolio id
        :return: list of Trade objects
        """
        buy_orders = self.order_service.get_all({
            "status": OrderStatus.CLOSED.value,
            "order_side": OrderSide.BUY.value,
            "portfolio_id": portfolio_id
        })
        return [
            Trade(
                buy_order_id=order.id,
                target_symbol=order.get_target_symbol(),
                trading_symbol=order.get_trading_symbol(),
                amount=order.get_amount(),
                open_price=order.get_price(),
                closed_price=order.get_trade_closed_price(),
                closed_at=order.get_trade_closed_at(),
                opened_at=order.get_created_at()
            ) for order in buy_orders
            if order.get_trade_closed_at() is not None
        ]

    def close_trade(self, trade, market=None, precision=None) -> None:
        """
        Close trade method

        param trade: Trade object
        param market: str representing the market
        raises OperationalException: if trade is already closed
        or if the buy order belonging to the trade has no amount

        return: None
        """

        if trade.closed_at is not None:
            raise OperationalException("Trade already closed.")

        order = self.order_service.get(trade.buy_order_id)

        if order.get_filled() <= 0:
            raise OperationalException(
                "Buy order belonging to the trade has no amount."
            )

        portfolio = self.portfolio_repository\
            .find({"position": order.position_id})
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": order.get_target_symbol()}
        )
        amount = order.get_amount()

        if precision is not None:
            amount = RoundingService.round_down(amount, precision)

        if position.get_amount() < amount:
            logger.warning(
                f"Order amount {amount} is larger then amount "
                f"of available {position.symbol} "
                f"position: {position.get_amount()}, "
                f"changing order amount to size of position"
            )
            amount = position.get_amount()

        symbol = order.get_symbol()
        ticker = self.market_data_source_service.get_ticker(
            symbol=symbol, market=market
        )
        self.order_service.create(
            {
                "portfolio_id": portfolio.id,
                "trading_symbol": order.get_trading_symbol(),
                "target_symbol": order.get_target_symbol(),
                "amount": amount,
                "order_side": OrderSide.SELL.value,
                "order_type": OrderType.LIMIT.value,
                "price": ticker["bid"],
            }
        )

    def count(self, query_params=None) -> int:
        """
        Count method

        :param query_params: dict representing the query parameters
        :return: int representing the count
        """

        portfolios = self.portfolio_repository.get_all()
        trades = []

        for portfolio in portfolios:
            buy_orders = self.order_service.get_all({
                "status": OrderStatus.CLOSED.value,
                "order_side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id
            })

            for buy_order in buy_orders:
                trades.append(
                    Trade(
                        buy_order_id=buy_order.id,
                        target_symbol=buy_order.get_target_symbol(),
                        trading_symbol=buy_order.get_trading_symbol(),
                        amount=buy_order.get_amount(),
                        open_price=buy_order.get_price(),
                        closed_price=buy_order.get_trade_closed_price(),
                        closed_at=buy_order.get_trade_closed_at(),
                        opened_at=buy_order.get_created_at(),
                    )
                )

            if query_params is not None:
                if "status" in query_params:

                    trade_status = TradeStatus\
                        .from_value(query_params["status"])

                    if trade_status == TradeStatus.OPEN:
                        trades = [
                            trade for trade in trades
                            if trade.closed_at is None
                        ]
                    else:
                        trades = [
                            trade for trade in trades
                            if trade.closed_at is not None
                        ]

        return len(trades)

    def close_trades(self, sell_order: Order, amount_to_close: float) -> None:
        """
        Close trades method

        :param sell_order: Order object representing the sell order
        :param amount_to_close: float representing the amount to close
        :return: None
        """
        logger.info(
            f"Closing trades for sell order {sell_order.get_id()} "
            f"amount to close: {amount_to_close}"
        )

        matching_buy_orders = self.order_service.get_all(
            {
                "position": sell_order.position_id,
                "order_side": OrderSide.BUY.value,
                "status": OrderStatus.CLOSED.value,
                "order_by_created_at_asc": True
            }
        )
        matching_buy_orders = [
            buy_order for buy_order in matching_buy_orders
            if buy_order.get_trade_closed_at() is None
        ]
        order_queue = PriorityQueue()

        for order in matching_buy_orders:
            order_queue.put(order)

        total_net_gain = 0
        total_cost = 0

        while amount_to_close > 0 and not order_queue.empty():
            buy_order = order_queue.get()
            closed_amount = buy_order.get_trade_closed_amount()

            # Check if the order has been closed
            if closed_amount is None:
                closed_amount = 0

            available_to_close = buy_order.get_filled() - closed_amount

            if amount_to_close >= available_to_close:
                to_be_closed = available_to_close
                remaining = amount_to_close - to_be_closed
                cost = buy_order.get_price() * to_be_closed
                net_gain = (sell_order.get_price() - buy_order.get_price()) \
                    * to_be_closed
                amount_to_close = remaining
                self.order_service.repository.update(
                    buy_order.id,
                    {
                        "trade_closed_amount": buy_order.get_filled(),
                        "trade_closed_at": sell_order.get_updated_at(),
                        "trade_closed_price": sell_order.get_price(),
                        "net_gain": buy_order.get_net_gain() + net_gain
                    }
                )
            else:
                to_be_closed = amount_to_close
                net_gain = (sell_order.get_price() - buy_order.get_price()) \
                    * to_be_closed
                cost = buy_order.get_price() * amount_to_close
                closed_amount = buy_order.get_trade_closed_amount()

                if closed_amount is None:
                    closed_amount = 0

                self.order_service.repository.update(
                    buy_order.id,
                    {
                        "trade_closed_amount": closed_amount + to_be_closed,
                        "trade_closed_price": sell_order.get_price(),
                        "net_gain": buy_order.get_net_gain() + net_gain
                    }
                )
                amount_to_close = 0

            total_net_gain += net_gain
            total_cost += cost

        # Update the sell order
        self.order_service.repository.update(
            sell_order.get_id(),
            {
                "trade_closed_amount": sell_order.get_filled(),
                "trade_closed_at": sell_order.get_updated_at(),
                "trade_closed_price": sell_order.get_price(),
                "net_gain": sell_order.get_net_gain() + total_net_gain
            }
        )
