import logging
from datetime import datetime, timezone
from queue import PriorityQueue
from typing import Union

from investing_algorithm_framework.domain import OrderStatus, TradeStatus, \
    Trade, OperationalException, TradeRiskType, OrderType, \
    OrderSide, MarketDataType, Environment, ENVIRONMENT, PeekableQueue, \
    BACKTESTING_INDEX_DATETIME, random_number, random_string
from investing_algorithm_framework.services.repository_service import \
    RepositoryService

logger = logging.getLogger(__name__)


class TradeService(RepositoryService):
    """
    Trade service class to handle trade related operations. This class
    is responsible for creating, updating, and deleting trades. It also
    takes care of keeping track of all sell transactions that are
    associated with a trade.
    """

    def __init__(
        self,
        trade_repository,
        order_repository,
        trade_stop_loss_repository,
        trade_take_profit_repository,
        position_repository,
        portfolio_repository,
        market_data_source_service,
        configuration_service,
        order_metadata_repository
    ):
        super(TradeService, self).__init__(trade_repository)
        self.order_repository = order_repository
        self.portfolio_repository = portfolio_repository
        self.market_data_source_service = market_data_source_service
        self.position_repository = position_repository
        self.configuration_service = configuration_service
        self.trade_stop_loss_repository = trade_stop_loss_repository
        self.trade_take_profit_repository = trade_take_profit_repository
        self.order_metadata_repository = order_metadata_repository

    def create_trade_from_buy_order(self, buy_order) -> Union[Trade, None]:
        """
        Function to create a trade from a buy order. If the given buy
        order has its status set to CANCELED, EXPIRED, or REJECTED,
        the trade object will not be created. If the given buy
        order has its status set to CLOSED or OPEN, the trade object
        will be created. The amount will be set to the filled amount.

        Args:
            buy_order: Order object representing the buy order

        Returns:
            Union[Trade, None] Representing the created trade object or None
        """

        if buy_order.status in \
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
            "amount": buy_order.get_amount(),
            "available_amount": buy_order.get_filled(),
            "filled_amount": buy_order.get_filled(),
            "remaining": buy_order.get_remaining(),
            "opened_at": buy_order.created_at,
            "cost": buy_order.get_filled() * buy_order.price
        }

        if buy_order.get_filled() > 0:
            data["status"] = TradeStatus.OPEN.value
            data["cost"] = buy_order.filled * buy_order.price

        return self.create(data)

    def _create_trade_metadata_with_sell_order(self, sell_order):
        """
        Function to create trade metadata with only a sell order.
        This function will create all metadata objects for the trades
        that are closed with the sell order amount.

        Args:
            sell_order: Order object representing the sell order

        Returns:
            None
        """
        position = self.position_repository.find({
            "order_id": sell_order.id
        })
        portfolio_id = position.portfolio_id
        matching_trades = self.get_all({
            "status": TradeStatus.OPEN.value,
            "target_symbol": sell_order.target_symbol,
            "portfolio_id": portfolio_id
        })
        updated_at = sell_order.updated_at
        total_available_to_close = 0
        amount_to_close = sell_order.amount
        trade_queue = PriorityQueue()
        sell_order_id = sell_order.id
        sell_price = sell_order.price

        for trade in matching_trades:
            if trade.available_amount > 0:
                total_available_to_close += trade.available_amount
                trade_queue.put(trade)

        if total_available_to_close < amount_to_close:
            raise OperationalException(
                "Not enough amount to close in trades."
            )

        # Create order metadata object
        while amount_to_close > 0 and not trade_queue.empty():
            trade = trade_queue.get()
            trade_id = trade.id
            available_to_close = trade.available_amount

            if amount_to_close >= available_to_close:
                amount_to_close = amount_to_close - available_to_close
                cost = trade.open_price * available_to_close
                net_gain = (sell_price * available_to_close) - cost
                update_data = {
                    "available_amount": 0,
                    "orders": trade.orders.append(sell_order),
                    "updated_at": updated_at,
                    "closed_at": updated_at,
                    "net_gain": trade.net_gain + net_gain
                }

                if trade.remaining == 0:
                    update_data["status"] = TradeStatus.CLOSED.value

                self.update(trade_id, update_data)
                self.repository.add_order_to_trade(trade, sell_order)

                # Create metadata object
                self.order_metadata_repository.\
                    create({
                        "order_id": sell_order_id,
                        "trade_id": trade_id,
                        "amount": available_to_close,
                        "amount_pending": available_to_close,
                    })
            else:
                to_be_closed = amount_to_close
                cost = trade.open_price * to_be_closed
                net_gain = (sell_price * to_be_closed) - cost

                self.update(
                    trade_id, {
                        "available_amount":
                            trade.available_amount - to_be_closed,
                        "orders": trade.orders.append(sell_order),
                        "updated_at": updated_at,
                        "net_gain": trade.net_gain + net_gain
                    }
                )
                self.repository.add_order_to_trade(trade, sell_order)

                # Create an order metadata object
                self.order_metadata_repository.\
                    create({
                        "order_id": sell_order_id,
                        "trade_id": trade_id,
                        "amount": to_be_closed,
                        "amount_pending": to_be_closed,
                    })

                amount_to_close = 0

    def _create_stop_loss_metadata_with_sell_order(
        self, sell_order_id, stop_losses
    ):
        """
        """
        sell_order = self.order_repository.get(sell_order_id)

        for stop_loss_data in stop_losses:

            self.order_metadata_repository.\
                create({
                    "order_id": sell_order.id,
                    "stop_loss_id": stop_loss_data["stop_loss_id"],
                    "amount": stop_loss_data["amount"],
                    "amount_pending": stop_loss_data["amount"]
                })

    def _create_take_profit_metadata_with_sell_order(
        self, sell_order_id, take_profits
    ):
        """
        """
        sell_order = self.order_repository.get(sell_order_id)

        for take_profit_data in take_profits:

            self.order_metadata_repository.\
                create({
                    "order_id": sell_order.id,
                    "take_profit_id": take_profit_data["take_profit_id"],
                    "amount": take_profit_data["amount"],
                    "amount_pending": take_profit_data["amount"]
                })

    def update(self, trade_id, data) -> Trade:
        """
        Function to update a trade object. This function will update
        the trade object with the given data.

        Args:
            trade_id: int representing the id of the trade object
            data: dict representing the data that should be updated

        Returns:
            Trade object
        """

        # Update the stop losses and take profits if last reported price
        # is updated
        if "last_reported_price" in data:
            trade = self.get(trade_id)
            stop_losses = trade.stop_losses
            to_be_saved_stop_losses = []
            take_profits = trade.take_profits
            to_be_saved_take_profits = []

            # Check if 'update_at' attribute is in data

            if 'last_reported_price_date' in data:
                last_reported_price_date = data["last_reported_price_date"]
            else:

                # Check if config environment has value BACKTEST
                config = self.configuration_service.get_config()
                environment = config[ENVIRONMENT]

                if Environment.BACKTEST.equals(environment):
                    last_reported_price_date = \
                        config[BACKTESTING_INDEX_DATETIME]
                else:
                    last_reported_price_date = \
                        datetime.now(tz=timezone.utc)

            for stop_loss in stop_losses:

                if stop_loss.active:
                    stop_loss.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_stop_losses.append(stop_loss)

            for take_profit in take_profits:

                if take_profit.active:
                    take_profit.update_with_last_reported_price(
                        data["last_reported_price"], last_reported_price_date
                    )
                    to_be_saved_take_profits.append(take_profit)

            self.trade_stop_loss_repository\
                .save_objects(to_be_saved_stop_losses)

            self.trade_take_profit_repository\
                .save_objects(to_be_saved_take_profits)

        return super(TradeService, self).update(trade_id, data)

    def _create_trade_metadata_with_sell_order_and_trades(
        self, sell_order, trades
    ):
        """
        Function to create trade metadata with a sell order and trades.

        The metadata objects function as a link between the trades and
        the sell order. The metadata objects are used to keep track
        of the trades that are closed with the sell order.

        A single sell order can close or partially close multiple trades.
        Therefore it is important to keep track of the trades that are
        closed with the sell order. The metadata objects are used to
        keep track of this relationship.


        """
        sell_order_id = sell_order.id
        updated_at = sell_order.updated_at
        sell_amount = sell_order.amount
        sell_price = sell_order.price

        for trade_data in trades:
            trade = self.get(trade_data["trade_id"])
            trade_id = trade.id
            open_price = trade.open_price
            old_net_gain = trade.net_gain
            available_amount = trade.available_amount
            filled_amount = trade.filled_amount
            amount = trade.amount

            self.order_metadata_repository.\
                create({
                    "order_id": sell_order_id,
                    "trade_id": trade_data["trade_id"],
                    "amount": trade_data["amount"],
                    "amount_pending": trade_data["amount"]
                })

            # Add the sell order to the trade
            self.repository.add_order_to_trade(trade, sell_order)

            # Update the trade
            net_gain = (sell_price * sell_amount) - open_price * sell_amount
            available_amount = available_amount - trade_data["amount"]
            trade_updated_data = {
                "available_amount": available_amount,
                "updated_at": updated_at,
                "net_gain": old_net_gain + net_gain
            }

            if available_amount == 0 and filled_amount == amount:
                trade_updated_data["status"] = TradeStatus.CLOSED.value
                trade_updated_data["closed_at"] = updated_at
            else:
                trade_updated_data["status"] = TradeStatus.OPEN.value

            # Update the trade object
            self.update(trade_id, trade_updated_data)

    def create_order_metadata_with_trade_context(
        self, sell_order, trades=None, stop_losses=None, take_profits=None
    ):
        """
        Function to create order metadata for trade related models.

        If only the sell order is provided, we assume that the sell order
        is initiated by a client of the order service. In this case we
        create only metadata objects for the trades based on size of the
        sell order.

        If also stop losses and take profits are provided, we assume that
        the sell order is initiated a stop loss or take profit. In this case
        we create metadata objects for the trades, stop losses,
        and take profits.

        If the trades param is provided, we assume that the sell order is
        based on either a stop loss or take profit or a closing of a trade.
        In this case we create also the metadata objects for the trades,

        As part of this function, we will also update the position cost.

        Scenario 1: Sell order without trades, stop losses, and take profits
        - Use the sell amount to create all trade metadata objects
        - Update the position cost

        Scenario 2: Sell order with trades
        - We assume that the sell amount is same as the total amount
            of the trades
        - Use the trades to create all trade metadata objects
        - Update trade object remaining amount
        - Update the position cost

        Scenario 3: Sell order with trades, stop losses, and take profits
        - We assume that the sell amount is same as the total
            amount of the trades
        - Use the trades to create all metadata objects
        - Update trade object remaining amount
        - Use the stop losses to create all metadata objects
        - Use the take profits to create all metadata objects
        - Update the position cost

        Args:
            sell_order: Order object representing the sell order that has
                been created

        Returns:
            None
        """
        sell_order_id = sell_order.id
        sell_price = sell_order.price

        if (trades is None or len(trades) == 0) \
                and (stop_losses is None or len(stop_losses) == 0) \
                and (take_profits is None or len(take_profits) == 0):
            self._create_trade_metadata_with_sell_order(sell_order)
        else:

            if stop_losses is not None:
                self._create_stop_loss_metadata_with_sell_order(
                    sell_order_id, stop_losses
                )

            if take_profits is not None:
                self._create_take_profit_metadata_with_sell_order(
                    sell_order_id, take_profits
                )

            if trades is not None:
                self._create_trade_metadata_with_sell_order_and_trades(
                    sell_order, trades
                )

        # Retrieve all trades metadata objects
        order_metadatas = self.order_metadata_repository.get_all({
            "order_id": sell_order_id
        })

        # Update the position cost
        position = self.position_repository.find({
            "order_id": sell_order_id
        })

        # Update position
        cost = 0
        net_gain = 0
        for metadata in order_metadatas:
            if metadata.trade_id is not None:
                trade = self.get(metadata.trade_id)
                cost += trade.open_price * metadata.amount
                net_gain += (sell_price * metadata.amount) - cost

        position.cost -= cost
        self.position_repository.save(position)

        # Update the net gain and net size of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain += net_gain
        portfolio.net_size += net_gain
        self.portfolio_repository.save(portfolio)

    def update_trade_with_removed_sell_order(
        self, sell_order
    ) -> Trade:
        """
        This function updates a trade with a removed sell order that belongs
        to the trade. This function uses the order metadata objects to
        update the trade object. The function will update the trade object
        available amount, cost, and net gain. The function will also
        update the stop loss and take profit objects that are associated
        with the trade object. The function will update the position cost
        and the portfolio net gain.

        Args:
            sell_order (Order): Order object representing the sell order
                that has been removed

        Returns:
            Trade: Trade object representing the updated trade object
        """
        position_cost = 0
        total_net_gain = 0

        # Get all order metadata objects that are associated with
        # the sell order
        order_metadatas = self.order_metadata_repository.get_all({
            "order_id": sell_order.id
        })

        for metadata in order_metadatas:
            # If trade id is not None, update the trade object
            if metadata.trade_id is not None:
                trade = self.get(metadata.trade_id)
                cost = metadata.amount_pending * trade.open_price
                net_gain = (sell_order.price * metadata.amount_pending) - cost
                trade.available_amount += metadata.amount_pending
                trade.status = TradeStatus.OPEN.value
                trade.updated_at = sell_order.updated_at
                trade.net_gain -= net_gain
                trade.cost += cost
                trade = self.save(trade)

                # Update the position cost
                position_cost += cost
                total_net_gain += net_gain

            if metadata.stop_loss_id is not None:
                stop_loss = self.trade_stop_loss_repository\
                    .get(metadata.stop_loss_id)
                stop_loss.sold_amount -= metadata.amount_pending
                stop_loss.remove_sell_price(
                    sell_order.price, sell_order.created_at
                )

                if stop_loss.sold_amount < stop_loss.sell_amount:
                    stop_loss.active = True
                    stop_loss.high_water_mark = None

                self.trade_stop_loss_repository.save(stop_loss)

            if metadata.take_profit_id is not None:
                take_profit = self.trade_take_profit_repository\
                    .get(metadata.take_profit_id)
                take_profit.sold_amount -= metadata.amount_pending
                take_profit.remove_sell_price(
                    sell_order.price, sell_order.created_at
                )

                if take_profit.sold_amount < take_profit.sell_amount:
                    take_profit.active = True
                    take_profit.high_water_mark = None

                self.trade_take_profit_repository.save(take_profit)

        # Update the position cost
        position = self.position_repository.find({
            "order_id": sell_order.id
        })
        position.cost += position_cost
        self.position_repository.save(position)

        # Update the net gain of the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio.total_net_gain -= total_net_gain
        portfolio.net_size -= total_net_gain
        self.portfolio_repository.save(portfolio)
        return trade

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
        filled = buy_order.get_filled()
        amount = buy_order.get_amount()

        if filled is None:
            filled = trade.filled_amount + filled_difference

        remaining = buy_order.get_remaining()

        if remaining is None:
            remaining = trade.remaining - filled_difference

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
            "available_amount": trade.available_amount + filled_difference,
            "filled_amount": filled,
            "remaining": remaining,
            "cost": trade.cost + filled_difference * buy_order.price
        }

        if amount != trade.amount:
            updated_data["amount"] = amount
            updated_data["cost"] = amount * buy_order.price

        if filled_difference > 0:
            updated_data["status"] = TradeStatus.OPEN.value

        trade = self.update(trade.id, updated_data)
        return trade

    def update_trade_with_filled_sell_order(
        self, filled_difference, sell_order
    ) -> Trade:
        """
        Function to update a trade with a filled sell order. This
        function will update all the metadata objects that where
        created by the sell order.


        """
        # Update all metadata objects
        metadata_objects = self.order_metadata_repository.get_all({
            "order_id": sell_order.id
        })

        trade_filled_difference = filled_difference
        stop_loss_filled_difference = filled_difference
        take_profit_filled_difference = filled_difference
        total_amount_in_metadata = 0
        trade_metadata_objects = []

        for metadata_object in metadata_objects:
            # Update the trade metadata object
            if metadata_object.trade_id is not None \
                    and trade_filled_difference > 0:

                trade_metadata_objects.append(metadata_object)
                total_amount_in_metadata += metadata_object.amount

                if metadata_object.amount_pending >= trade_filled_difference:
                    amount = trade_filled_difference
                    trade_filled_difference = 0
                else:
                    amount = metadata_object.amount_pending
                    trade_filled_difference -= amount

                metadata_object.amount_pending -= amount
                self.order_metadata_repository.save(metadata_object)

            if metadata_object.stop_loss_id is not None \
                    and stop_loss_filled_difference > 0:

                if (
                    metadata_object.amount_pending >=
                    stop_loss_filled_difference
                ):
                    amount = stop_loss_filled_difference
                    stop_loss_filled_difference = 0
                else:
                    amount = metadata_object.amount_pending
                    stop_loss_filled_difference -= amount

                metadata_object.amount_pending -= amount
                self.order_metadata_repository.save(metadata_object)

            if metadata_object.take_profit_id is not None \
                    and take_profit_filled_difference > 0:

                if (
                    metadata_object.amount_pending >=
                    take_profit_filled_difference
                ):
                    amount = take_profit_filled_difference
                    take_profit_filled_difference = 0
                else:
                    amount = metadata_object.amount_pending
                    take_profit_filled_difference -= amount

                metadata_object.amount_pending -= amount
                self.order_metadata_repository.save(metadata_object)

        # Update trade available amount if the total amount in metadata
        # is not equal to the sell order amount
        if total_amount_in_metadata != sell_order.amount:
            difference = sell_order.amount - total_amount_in_metadata
            trades = []

            for metadata_object in trade_metadata_objects:
                trade = self.get(metadata_object.trade_id)
                trades.append(trade)

            # Sort trades by created_at with the most recent first
            trades = sorted(
                trades,
                key=lambda x: x.updated_at,
                reverse=True
            )
            queue = PeekableQueue(trades)

            while difference != 0 and not queue.is_empty():
                trade = queue.dequeue()
                trade.available_amount -= difference
                self.save(trade)

    def update_trades_with_market_data(self, market_data):
        """
        Function to update trades with market data. This function will
        update the last reported price and last reported price date of the
        trade.

        Args:
            market_data: dict representing the market data
                that will be used to update the trades

        Returns:
            None
        """
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
                "last_reported_price_datetime": last_row["Datetime"][0],
                "updated_at": last_row["Datetime"][0]
            }
            self.update(open_trade.id, update_data)

    def add_stop_loss(
        self,
        trade,
        percentage: float,
        trade_risk_type: TradeRiskType = TradeRiskType.FIXED,
        sell_percentage: float = 100,
    ):
        """
        Function to add a stop loss to a trade.

        Example of fixed stop loss:
            * You buy BTC at $40,000.
            * You set a SL of 5% → SL level at $38,000 (40,000 - 5%).
            * BTC price increases to $42,000 → SL level remains at $38,000.
            * BTC price drops to $38,000 → SL level reached, trade closes.

        Example of trailing stop loss:
            * You buy BTC at $40,000.
            * You set a TSL of 5%, setting the sell price at $38,000.
            * BTC price increases to $42,000 → New TSL level at
                $39,900 (42,000 - 5%).
            * BTC price drops to $39,900 → SL level reached, trade closes.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trade_risk_type (TradeRiskType): The type of the stop loss, fixed
                or trailing
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered

        Returns:
            None
        """
        trade = self.get(trade.id)

        # Check if the sell percentage + the existing stop losses is
        # greater than 100
        existing_sell_percentage = 0
        for stop_loss in trade.stop_losses:
            existing_sell_percentage += stop_loss.sell_percentage

        if existing_sell_percentage + sell_percentage > 100:
            raise OperationalException(
                "Combined sell percentages of stop losses belonging "
                "to trade exceeds 100."
            )

        creation_data = {
            "trade_id": trade.id,
            "trade_risk_type": TradeRiskType.from_value(trade_risk_type).value,
            "percentage": percentage,
            "open_price": trade.open_price,
            "total_amount_trade": trade.amount,
            "sell_percentage": sell_percentage,
            "active": True
        }
        return self.trade_stop_loss_repository.create(creation_data)

    def add_take_profit(
        self,
        trade,
        percentage: float,
        trade_risk_type: TradeRiskType = TradeRiskType.FIXED,
        sell_percentage: float = 100,
    ) -> None:
        """
        Function to add a take profit to a trade. This function will add a
        take profit to the specified trade. If the take profit is triggered,
        the trade will be closed.

        Example of take profit:
            * You buy BTC at $40,000.
            * You set a TP of 5% → TP level at $42,000 (40,000 + 5%).
            * BTC rises to $42,000 → TP level reached, trade
                closes, securing profit.

        Example of trailing take profit:
            * You buy BTC at $40,000
            * You set a TTP of 5%, setting the sell price at $42,000.
            * BTC rises to $42,000 → TTP level stays at $42,000.
            * BTC rises to $45,000 → New TTP level at $42,750.
            * BTC drops to $42,750 → Trade closes, securing profit.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trade_risk_type (TradeRiskType): The type of the stop loss, fixed
                or trailing
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered

        Returns:
            None
        """
        trade = self.get(trade.id)

        # Check if the sell percentage + the existing stop losses is
        # greater than 100
        existing_sell_percentage = 0
        for take_profit in trade.take_profits:
            existing_sell_percentage += take_profit.sell_percentage

        if existing_sell_percentage + sell_percentage > 100:
            raise OperationalException(
                "Combined sell percentages of stop losses belonging "
                "to trade exceeds 100."
            )

        creation_data = {
            "trade_id": trade.id,
            "trade_risk_type": TradeRiskType.from_value(trade_risk_type).value,
            "percentage": percentage,
            "open_price": trade.open_price,
            "total_amount_trade": trade.amount,
            "sell_percentage": sell_percentage,
            "active": True
        }
        return self.trade_take_profit_repository.create(creation_data)

    def get_triggered_stop_loss_orders(self):
        """
        Function to get all triggered stop loss orders. This function will
        return a list of trade ids that have triggered stop losses.

        Returns:
            List of trade ids
        """
        triggered_stop_losses = {}
        sell_orders_data = []
        query = {"status": TradeStatus.OPEN.value}
        open_trades = self.get_all(query)
        to_be_saved_stop_loss_objects = []

        # Group trades by target symbol
        stop_losses_by_target_symbol = {}

        for open_trade in open_trades:
            triggered_stop_losses = []

            for stop_loss in open_trade.stop_losses:

                if (
                    stop_loss.active
                    and stop_loss.has_triggered(open_trade.last_reported_price)
                ):
                    triggered_stop_losses.append(stop_loss)

                to_be_saved_stop_loss_objects.append(stop_loss)

            if len(triggered_stop_losses) > 0:
                stop_losses_by_target_symbol[open_trade] = \
                    triggered_stop_losses

        for trade in stop_losses_by_target_symbol:
            stop_losses = stop_losses_by_target_symbol[trade]
            available_amount = trade.available_amount
            stop_loss_que = PeekableQueue(stop_losses)
            order_amount = 0
            stop_loss_metadata = []

            # While there is an available amount and there are stop losses
            # to process
            while not stop_loss_que.is_empty() and available_amount > 0:
                stop_loss = stop_loss_que.dequeue()
                stop_loss_sell_amount = stop_loss.get_sell_amount()

                if stop_loss_sell_amount <= available_amount:
                    available_amount = available_amount - stop_loss_sell_amount
                    stop_loss.active = False
                    stop_loss.sold_amount += stop_loss_sell_amount
                    order_amount += stop_loss_sell_amount
                else:
                    stop_loss.sold_amount += available_amount

                    # Deactivate stop loss if the filled amount is equal
                    # to the amount of the trade, meaning that there is
                    # nothing left to sell
                    if trade.filled_amount == trade.amount:
                        stop_loss.active = False
                    else:
                        stop_loss.active = True

                    order_amount += available_amount
                    stop_loss_sell_amount = available_amount
                    available_amount = 0

                stop_loss_metadata.append({
                    "stop_loss_id": stop_loss.id,
                    "amount": stop_loss_sell_amount
                })
                stop_loss.add_sell_price(
                    trade.last_reported_price,
                    trade.last_reported_price_datetime
                )

            position = self.position_repository.find({
                "order_id": trade.orders[0].id
            })
            portfolio_id = position.portfolio_id
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio_id,
                    "stop_losses": stop_loss_metadata,
                    "trades": [{
                        "trade_id": trade.id,
                        "amount": order_amount
                    }]
                }
            )

        self.trade_stop_loss_repository\
            .save_objects(to_be_saved_stop_loss_objects)
        return sell_orders_data

    def get_triggered_take_profit_orders(self):
        """
        Function to get all triggered stop loss orders. This function will
        return a list of trade ids that have triggered stop losses.

        Returns:
            List of trade objects. A trade object is a dictionary

        """
        triggered_take_profits = {}
        sell_orders_data = []
        query = {"status": TradeStatus.OPEN.value}
        open_trades = self.get_all(query)
        to_be_saved_take_profit_objects = []

        # Group trades by target symbol
        take_profits_by_target_symbol = {}

        for open_trade in open_trades:
            triggered_take_profits = []
            available_amount = open_trade.available_amount

            # Skip if there is no available amount
            if available_amount == 0:
                continue

            for take_profit in open_trade.take_profits:

                if (
                    take_profit.active and
                    take_profit.has_triggered(open_trade.last_reported_price)
                ):
                    triggered_take_profits.append(take_profit)

                to_be_saved_take_profit_objects.append(take_profit)

            if len(triggered_take_profits) > 0:
                take_profits_by_target_symbol[open_trade] = \
                    triggered_take_profits

        for trade in take_profits_by_target_symbol:
            take_profits = take_profits_by_target_symbol[trade]
            available_amount = trade.available_amount
            take_profit_que = PeekableQueue(take_profits)
            order_amount = 0
            take_profit_metadata = []

            # While there is an available amount and there are take profits
            # to process
            while not take_profit_que.is_empty() and available_amount > 0:
                take_profit = take_profit_que.dequeue()
                take_profit_sell_amount = take_profit.get_sell_amount()

                if take_profit_sell_amount <= available_amount:
                    available_amount = available_amount - \
                        take_profit_sell_amount
                    take_profit.active = False
                    take_profit.sold_amount += take_profit_sell_amount
                    order_amount += take_profit_sell_amount
                else:
                    take_profit.sold_amount += available_amount

                    # Deactivate take profit if the filled amount is equal
                    # to the amount of the trade, meaning that there is
                    # nothing left to sell
                    if trade.filled_amount == trade.amount:
                        take_profit.active = False
                    else:
                        take_profit.active = True

                    order_amount += available_amount
                    take_profit_sell_amount = available_amount
                    available_amount = 0

                take_profit_metadata.append({
                    "take_profit_id": take_profit.id,
                    "amount": take_profit_sell_amount
                })

                take_profit.add_sell_price(
                    trade.last_reported_price,
                    trade.last_reported_price_datetime
                )

            position = self.position_repository.find({
                "order_id": trade.orders[0].id
            })
            portfolio_id = position.portfolio_id
            sell_orders_data.append(
                {
                    "target_symbol": trade.target_symbol,
                    "trading_symbol": trade.trading_symbol,
                    "amount": order_amount,
                    "price": trade.last_reported_price,
                    "order_type": OrderType.LIMIT.value,
                    "order_side": OrderSide.SELL.value,
                    "portfolio_id": portfolio_id,
                    "take_profits": take_profit_metadata,
                    "trades": [{
                        "trade_id": trade.id,
                        "amount": order_amount
                    }]
                }
            )

        self.trade_take_profit_repository\
            .save_objects(to_be_saved_take_profit_objects)
        return sell_orders_data

    def _create_order_id(self) -> str:
        """
        Function to create a unique order id. This function will
        create a unique order id based on the current time and
        the order id counter.

        Returns:
            str: Unique order id
        """
        unique = False
        order_id = None

        while not unique:
            order_id = f"{random_number(8)}-{random_string(8)}"

            if not self.exists({"order_id": order_id}):
                unique = True

        return order_id
