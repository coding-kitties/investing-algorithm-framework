from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from investing_algorithm_framework.domain import OperationalException, Position
from investing_algorithm_framework.domain import PositionSize, \
    TimeUnit, StrategyProfile, Trade, DataSource, OrderSide
from .context import Context


class TradingStrategy:
    """
    TradingStrategy is the base class for all trading strategies. A trading
    strategy is a set of rules that defines when to buy or sell an asset.

    Attributes:
        time_unit: TimeUnit - the time unit of the strategy that defines
            when the strategy should run e.g. HOUR, DAY, WEEK, MONTH
        interval: int - the interval of the strategy that defines how often
            the strategy should run within the time unit e.g. every 5 hours,
            every 2 days, every 3 weeks, every 4 months
        worker_id (optional): str - the id of the worker
        strategy_id (optional): str - the id of the strategy
        decorated (optional): function - the decorated function
        data_sources (List[DataSource] optional): the list of data
            sources to use for the strategy. The data sources will be used
            to indentify data providers that will be called to gather data
            and pass to the strategy before its run.
        metadata (optional): Dict[str, Any] - a dictionary
            containing metadata about the strategy. This can be used to
            store additional information about the strategy, such as its
            author, version, description, params etc.
    """
    time_unit: TimeUnit = None
    interval: int = None
    worker_id: str = None
    strategy_id: str = None
    decorated = None
    data_sources: List[DataSource] = []
    traces = None
    context: Context = None
    metadata: Dict[str, Any] = None
    position_sizes: List[PositionSize] = []
    symbols: List[str] = []
    trading_symbol: str = None

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        data_sources=None,
        metadata=None,
        position_sizes=None,
        symbols=None,
        trading_symbol=None,
        worker_id=None,
        decorated=None
    ):
        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)
        else:
            # Check if time_unit is None
            if self.time_unit is None:
                raise OperationalException(
                    f"Time unit attribute not set for "
                    f"strategy instance {self.strategy_id}"
                )

            self.time_unit = TimeUnit.from_value(self.time_unit)

        if interval is not None:
            self.interval = interval

        if data_sources is not None:
            self.data_sources = data_sources

        self.metadata = metadata

        if decorated is not None:
            self.decorated = decorated

        if worker_id is not None:
            self.worker_id = worker_id
        elif self.decorated:
            self.worker_id = decorated.__name__
        else:
            self.worker_id = self.__class__.__name__

        if strategy_id is not None:
            self.strategy_id = strategy_id
        else:
            self.strategy_id = self.worker_id

        if position_sizes is not None:
            self.position_sizes = position_sizes

        if symbols is not None:
            self.symbols = symbols

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol

        # Check if interval is None
        if self.interval is None:
            raise OperationalException(
                f"Interval not set for strategy instance {self.strategy_id}"
            )

        # context initialization
        self._context = None
        self._last_run = None

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Function that needs to be implemented by the user.
        This function should return a pandas Series containing the buy signals.

        Args:
            data (Dict[str, Any]): All the data that matched the
                data sources of the strategy.

        Returns:
            Dict[str, Series]: A dictionary where the keys are the
              symbols and the values are pandas Series containing
              the buy signals.
        """
        raise NotImplementedError(
            "generate_buy_signals method not implemented"
        )

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Function that needs to be implemented by the user.
        This function should return a pandas Series containing
        the sell signals.

        Args:
            data (Dict[str, Any]): All the data that matched the
                data sources of the strategy.

        Returns:
            Dict[str, Series]: A dictionary where the keys are the
                symbols and the values are pandas Series containing
                the sell signals.
        """
        raise NotImplementedError(
            "generate_sell_signals method not implemented"
        )

    def run_strategy(self, context: Context, data: Dict[str, Any]):
        """
        Main function for running your strategy. This function will be called
        by the framework when the trigger of your strategy is met.

        During execution of this function, the context and market data
        will be passed to the function. The context is an instance of
        the Context class, this class has various methods to do operations
        with your portfolio, orders, trades, positions and other components.

        The market data is a dictionary containing all the data retrieved
        from the specified data sources.

        Args:
            context (Context): The context of the strategy. This is an instance
                of the Context class, this class has various methods to do
                operations with your portfolio, orders, trades, positions and
                other components.
            data (Dict[str, Any]): The data for the strategy.
                This is a dictionary containing all the data retrieved from the
                specified data sources.

        Returns:
            None
        """
        self.context = context
        buy_signals = self.generate_buy_signals(data)
        sell_signals = self.generate_sell_signals(data)

        for symbol in self.symbols:

            if self.has_open_orders(symbol):
                continue

            if not self.has_position(symbol) \
                    and not self.has_open_orders(symbol):

                if symbol in buy_signals:
                    signals = buy_signals[symbol]

                    # Check in the last row if there is a buy signal
                    last_row = signals.iloc[-1]
                    if last_row:
                        position_size = next(
                            (ps for ps in self.position_sizes
                             if ps.symbol == symbol), None
                        )
                        if position_size is None:
                            raise OperationalException(
                                f"No position size defined for symbol "
                                f"{symbol} in strategy "
                                f"{self.strategy_id}"
                            )
                        full_symbol = (f"{symbol}/"
                                       f"{self.context.get_trading_symbol()}")
                        price = self.context.get_latest_price(full_symbol)
                        amount = position_size.get_size(
                            self.context.get_portfolio(), price
                        )
                        order_amount = amount / price
                        self.create_limit_order(
                            target_symbol=symbol,
                            order_side=OrderSide.BUY,
                            amount=order_amount,
                            price=price,
                            execute=True,
                            validate=True,
                            sync=True
                        )

            if self.has_position(symbol) \
                    and not self.has_open_orders(symbol):

                # Check in the last row if there is a sell signal
                if symbol in sell_signals:
                    signals = sell_signals[symbol]

                    # Check in the last row if there is a sell signal
                    last_row = signals.iloc[-1]

                    if last_row:
                        position = self.get_position(symbol)

                        if position is None:
                            raise OperationalException(
                                f"No position found for symbol {symbol} "
                                f"in strategy {self.strategy_id}"
                            )

                        full_symbol = (f"{symbol}/"
                                       f"{self.context.get_trading_symbol()}")
                        price = self.context.get_latest_price(full_symbol)
                        self.create_limit_order(
                            target_symbol=symbol,
                            order_side=OrderSide.SELL,
                            amount=position.amount,
                            execute=True,
                            validate=True,
                            sync=True,
                            price=price
                        )

    def apply_strategy(self, context, data):
        if self.decorated:
            self.decorated(context=context, data=data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.worker_id,
            interval=self.interval,
            time_unit=self.time_unit,
            data_sources=self.data_sources
        )

    def _update_trades_and_orders(self, market_data):
        self.context.order_service.check_pending_orders()
        self.context.trade_service\
            .update_trades_with_market_data(market_data)

    def _update_trades_and_orders_for_backtest(self, market_data):
        self.context.order_service.check_pending_orders(market_data)
        self.context.trade_service\
            .update_trades_with_market_data(market_data)

    def _check_stop_losses(self):
        """
        Check if there are any stop losses that result in trades being closed.
        """
        trade_service = self.context.trade_service

        stop_losses_orders_data = trade_service\
            .get_triggered_stop_loss_orders()

        order_service = self.context.order_service

        for stop_loss_order in stop_losses_orders_data:
            order_service.create(stop_loss_order)

    def _check_take_profits(self):
        """
        Check if there are any take profits that result in trades being closed.
        """
        trade_service = self.context.trade_service
        take_profit_orders_data = trade_service.\
            get_triggered_take_profit_orders()
        order_service = self.context.order_service

        for take_profit_order in take_profit_orders_data:
            order_service.create(take_profit_order)

    def on_trade_closed(self, context: Context, trade: Trade):
        pass

    def on_trade_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_created(self, context: Context, trade: Trade):
        pass

    def on_trade_opened(self, context: Context, trade: Trade):
        pass

    def on_trade_stop_loss_triggered(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_triggered(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_triggered(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_stop_loss_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_updated(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_stop_loss_created(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_created(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_created(self, context: Context, trade: Trade):
        pass

    @property
    def strategy_identifier(self):

        if self.strategy_id is not None:
            return self.strategy_id

        return self.worker_id

    def has_open_orders(
        self, target_symbol=None, identifier=None, market=None
    ) -> bool:
        """
        Check if there are open orders for a given symbol

        Args:
            target_symbol (str): The symbol of the asset e.g BTC if the
              asset is BTC/USDT
            identifier (str): The identifier of the portfolio
            market (str): The market of the asset

        Returns:
            bool: True if there are open orders, False otherwise
        """
        return self.context.has_open_orders(
            target_symbol=target_symbol, identifier=identifier, market=market
        )

    def create_limit_order(
        self,
        target_symbol,
        price,
        order_side,
        amount=None,
        amount_trading_symbol=None,
        percentage=None,
        percentage_of_portfolio=None,
        percentage_of_position=None,
        precision=None,
        market=None,
        execute=True,
        validate=True,
        sync=True
    ):
        """
        Function to create a limit order. This function will create
        a limit order and execute it if the execute parameter is set to True.
        If the validate parameter is set to True, the order will be validated

        Args:
            target_symbol: The symbol of the asset to trade
            price: The price of the asset
            order_side: The side of the order
            amount (optional): The amount of the asset to trade
            amount_trading_symbol (optional): The amount of the trading
              symbol to trade
            percentage (optional): The percentage of the portfolio to
                allocate to the order
            percentage_of_portfolio (optional): The percentage of
              the portfolio to allocate to the order
            percentage_of_position (optional): The percentage of
              the position to allocate to the order.
              (Only supported for SELL orders)
            precision (optional): The precision of the amount
            market (optional): The market to trade the asset
            execute (optional): Default True. If set to True, the order
              will be executed
            validate (optional): Default True. If set to True, the order
              will be validated
            sync (optional): Default True. If set to True, the created
              order will be synced with the portfolio of the context

        Returns:
            Order: Instance of the order created
        """
        self.context.create_limit_order(
            target_symbol=target_symbol,
            price=price,
            order_side=order_side,
            amount=amount,
            amount_trading_symbol=amount_trading_symbol,
            percentage=percentage,
            percentage_of_portfolio=percentage_of_portfolio,
            percentage_of_position=percentage_of_position,
            precision=precision,
            market=market,
            execute=execute,
            validate=validate,
            sync=sync
        )

    def close_position(
        self, symbol, market=None, identifier=None, precision=None
    ):
        """
        Function to close a position. This function will close a position
        by creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            symbol: The symbol of the asset
            market: The market of the asset
            identifier: The identifier of the portfolio
            precision: The precision of the amount

        Returns:
            None
        """
        self.context.close_position(
            symbol=symbol,
            market=market,
            identifier=identifier,
            precision=precision
        )

    def get_positions(
        self,
        market=None,
        identifier=None,
        amount_gt=None,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ) -> List[Position]:
        """
        Function to get all positions. This function will return all
        positions that match the specified query parameters. If the
        market parameter is specified, the positions of the specified
        market will be returned. If the identifier parameter is
        specified, the positions of the specified portfolio will be
        returned. If the amount_gt parameter is specified, the positions
        with an amount greater than the specified amount will be returned.
        If the amount_gte parameter is specified, the positions with an
        amount greater than or equal to the specified amount will be
        returned. If the amount_lt parameter is specified, the positions
        with an amount less than the specified amount will be returned.
        If the amount_lte parameter is specified, the positions with an
        amount less than or equal to the specified amount will be returned.

        Args:
            market: The market of the portfolio where the positions are
            identifier: The identifier of the portfolio
            amount_gt: The amount of the asset must be greater than this
            amount_gte: The amount of the asset must be greater than or
                equal to this
            amount_lt: The amount of the asset must be less than this
            amount_lte: The amount of the asset must be less than or equal
                to this

        Returns:
            List[Position]: A list of positions that match the query parameters
        """
        return self.context.get_positions(
            market=market,
            identifier=identifier,
            amount_gt=amount_gt,
            amount_gte=amount_gte,
            amount_lt=amount_lt,
            amount_lte=amount_lte
        )

    def get_trades(self, market=None) -> List[Trade]:
        """
        Function to get all trades. This function will return all trades
        that match the specified query parameters. If the market parameter
        is specified, the trades with the specified market will be returned.

        Args:
            market: The market of the asset

        Returns:
            List[Trade]: A list of trades that match the query parameters
        """
        return self.context.get_trades(market)

    def get_closed_trades(self) -> List[Trade]:
        """
        Function to get all closed trades. This function will return all
        closed trades of the context.

        Returns:
            List[Trade]: A list of closed trades
        """
        return self.context.get_closed_trades()

    def get_open_trades(self, target_symbol=None, market=None) -> List[Trade]:
        """
        Function to get all open trades. This function will return all
        open trades that match the specified query parameters. If the
        target_symbol parameter is specified, the open trades with the
        specified target symbol will be returned. If the market parameter
        is specified, the open trades with the specified market will be
        returned.

        Args:
            target_symbol: The symbol of the asset
            market: The market of the asset

        Returns:
            List[Trade]: A list of open trades that match the query parameters
        """
        return self.context.get_open_trades(target_symbol, market)

    def close_trade(self, trade, market=None, precision=None) -> None:
        """
        Function to close a trade. This function will close a trade by
        creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            trade: Trade - The trade to close
            market: str - The market of the trade
            precision: float - The precision of the amount

        Returns:
            None
        """
        self.context.close_trade(
            trade=trade, market=market, precision=precision
        )

    def get_number_of_positions(self):
        """
        Returns the number of positions that have a positive amount.

        Returns:
            int: The number of positions
        """
        return self.context.get_number_of_positions()

    def get_position(
        self, symbol, market=None, identifier=None
    ) -> Position:
        """
        Function to get a position. This function will return the
        position that matches the specified query parameters. If the
        market parameter is specified, the position of the specified
        market will be returned. If the identifier parameter is
        specified, the position of the specified portfolio will be
        returned.

        Args:
            symbol: The symbol of the asset that represents the position
            market: The market of the portfolio where the position is located
            identifier: The identifier of the portfolio

        Returns:
            Position: The position that matches the query parameters
        """
        return self.context.get_position(
            symbol=symbol,
            market=market,
            identifier=identifier
        )

    def has_position(
        self,
        symbol,
        market=None,
        identifier=None,
        amount_gt=0,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ):
        """
        Function to check if a position exists. This function will return
        True if a position exists, False otherwise. This function will check
        if the amount > 0 condition by default.

        Args:
            param symbol: The symbol of the asset
            param market: The market of the asset
            param identifier: The identifier of the portfolio
            param amount_gt: The amount of the asset must be greater than this
            param amount_gte: The amount of the asset must be greater than
            or equal to this
            param amount_lt: The amount of the asset must be less than this
            param amount_lte: The amount of the asset must be less than
            or equal to this

        Returns:
            Boolean: True if a position exists, False otherwise
        """
        return self.context.has_position(
            symbol=symbol,
            market=market,
            identifier=identifier,
            amount_gt=amount_gt,
            amount_gte=amount_gte,
            amount_lt=amount_lt,
            amount_lte=amount_lte
        )

    def has_balance(self, symbol, amount, market=None):
        """
        Function to check if the portfolio has enough balance to
        create an order. This function will return True if the
        portfolio has enough balance to create an order, False
        otherwise.

        Args:
            symbol: The symbol of the asset
            amount: The amount of the asset
            market: The market of the asset

        Returns:
            Boolean: True if the portfolio has enough balance
        """
        return self.context.has_balance(symbol, amount, market)

    def last_run(self) -> datetime:
        """
        Function to get the last run of the strategy

        Returns:
            DateTime: The last run of the strategy
        """
        return self.context.last_run()
