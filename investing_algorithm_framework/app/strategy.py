from typing import List
import pandas as pd
from datetime import datetime, timezone

from investing_algorithm_framework.domain import OperationalException, Position
from investing_algorithm_framework.domain import \
    TimeUnit, StrategyProfile, Trade, ENVIRONMENT, Environment, \
    BACKTESTING_INDEX_DATETIME
from .algorithm import Algorithm


class TradingStrategy:
    time_unit: str = None
    interval: int = None
    worker_id: str = None
    strategy_id: str = None
    decorated = None
    market_data_sources = None
    traces = None
    algorithm: Algorithm = None

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        market_data_sources=None,
        worker_id=None,
        decorated=None
    ):

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if interval is not None:
            self.interval = interval

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if market_data_sources is not None:
            self.market_data_sources = market_data_sources

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

        # Check if time_unit is None
        if self.time_unit is None:
            raise OperationalException(
                f"Time unit not set for strategy instance {self.strategy_id}"
            )

        # Check if interval is None
        if self.interval is None:
            raise OperationalException(
                f"Interval not set for strategy instance {self.strategy_id}"
            )

        # context initialization
        self._context = None
        self._last_run = None

    def run_strategy(self, algorithm, market_data):
        self.algorithm = algorithm

        # Check if there are any pending orders that need to be executed
        self._update_trade_prices()
        self._check_pending_orders(market_data)
        self._check_stop_losses(market_data)

        # Run user defined strategy
        self.apply_strategy(algorithm=algorithm, market_data=market_data)

        config = self.algorithm.get_config()

        if config[ENVIRONMENT] == Environment.BACKTEST.value:
            self._last_run = config[BACKTESTING_INDEX_DATETIME]
        else:
            self._last_run = datetime.now(tz=timezone.utc)

    def apply_strategy(self, algorithm, market_data):
        if self.decorated:
            self.decorated(algorithm=algorithm, market_data=market_data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.worker_id,
            interval=self.interval,
            time_unit=self.time_unit,
            market_data_sources=self.market_data_sources
        )

    def _check_pending_orders(self, market_data):
        """
        Check if there are any pending orders that need to be executed
        """
        self.algorithm.check_pending_orders()

    def _check_stop_losses(self, market_data):
        """
        Check if there are any stop losses that need
        to be triggered
        """
        trades = self.algorithm.get_open_trades()

    def _update_trade_prices(self):
        """
        Update the prices of the trades
        """
        trades = self.algorithm.get_open_trades()
        trade_service = self.algorithm.get_trade_service()

        for trade in trades:
            symbol = trade.get_symbol()
            market_data_source_service = \
                self.algorithm.get_market_data_source_service()
            ticker = market_data_source_service.get_ticker(symbol)
            print(ticker)

            if ticker is not None:
                trade_service.update(
                    trade.id, {"current_price": ticker["last"]}
                )

    def on_trade_closed(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_opened(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_triggered(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_stop_loss_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_updated(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_created(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_created(self, algorithm: Algorithm, trade: Trade):
        pass

    @property
    def strategy_identifier(self):

        if self.strategy_id is not None:
            return self.strategy_id

        return self.worker_id

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, context):
        self._context = context

    def add_trace(
        self,
        symbol: str,
        data,
        drop_duplicates=True
    ) -> None:
        """
        Add data to the straces object for a given symbol

        Args:
            symbol (str): The symbol
            data (pd.DataFrame): The data to add to the tracing
            drop_duplicates (bool): Drop duplicates

        Returns:
            None
        """

        # Check if data is a DataFrame
        if not isinstance(data, pd.DataFrame):
            raise ValueError(
                "Currently only pandas DataFrames are "
                "supported as tracing data objects."
            )

        data: pd.DataFrame = data

        # Check if index is a datetime object
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Dataframe Index must be a datetime object.")

        if self.traces is None:
            self.traces = {}

        # Check if the key is already in the context dictionary
        if symbol in self.traces:
            # If the key is already in the context dictionary,
            # append the new data to the existing data
            combined = pd.concat([self.traces[symbol], data])
        else:
            # If the key is not in the context dictionary,
            # add the new data to the context dictionary
            combined = data

        if drop_duplicates:
            # Drop duplicates and sort the data by the index
            combined = combined[~combined.index.duplicated(keep='first')]

        # Set the datetime column as the index
        combined.set_index(pd.DatetimeIndex(combined.index), inplace=True)
        self.traces[symbol] = combined

    def get_traces(self) -> dict:
        """
        Get the traces object

        Returns:
            dict: The traces object
        """
        return self.traces

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
        return self.algorithm.has_open_orders(
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
              order will be synced with the portfolio of the algorithm

        Returns:
            Order: Instance of the order created
        """
        self.algorithm.create_limit_order(
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

    def create_market_order(
        self,
        target_symbol,
        order_side,
        amount,
        market=None,
        execute=False,
        validate=False,
        sync=True
    ):
        """
        Function to create a market order. This function will create a market
        order and execute it if the execute parameter is set to True. If the
        validate parameter is set to True, the order will be validated

        Args:
            target_symbol: The symbol of the asset to trade
            order_side: The side of the order
            amount: The amount of the asset to trade
            market: The market to trade the asset
            execute: If set to True, the order will be executed
            validate: If set to True, the order will be validated
            sync: If set to True, the created order will be synced with the
                portfolio of the algorithm

        Returns:
            Order: Instance of the order created
        """
        self.algorithm.create_market_order(
            target_symbol=target_symbol,
            order_side=order_side,
            amount=amount,
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
        self.algorithm.close_position(
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
        return self.algorithm.get_positions(
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
        return self.algorithm.get_trades(market)

    def get_closed_trades(self) -> List[Trade]:
        """
        Function to get all closed trades. This function will return all
        closed trades of the algorithm.

        Returns:
            List[Trade]: A list of closed trades
        """
        return self.algorithm.get_closed_trades()

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
        return self.algorithm.get_open_trades(target_symbol, market)

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
        self.algorithm.close_trade(
            trade=trade, market=market, precision=precision
        )

    def get_number_of_positions(self):
        """
        Returns the number of positions that have a positive amount.

        Returns:
            int: The number of positions
        """
        return self.algorithm.get_number_of_positions()

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
        return self.algorithm.get_position(
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
        return self.algorithm.has_position(
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
        return self.algorithm.has_balance(symbol, amount, market)

    def last_run(self) -> datetime:
        """
        Function to get the last run of the strategy

        Returns:
            DateTime: The last run of the strategy
        """
        return self.algorithm.last_run()