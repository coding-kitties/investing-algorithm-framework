import logging
from datetime import datetime
from typing import List, Dict, Any, Union

import pandas as pd

from investing_algorithm_framework.domain import OperationalException, \
    Position, PositionSize, TimeUnit, StrategyProfile, Trade, \
    DataSource, DataType, OrderSide, StopLossRule, TakeProfitRule, Order, \
    INDEX_DATETIME, ScalingRule, TradingCost
from .context import Context

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    TradingStrategy is the base class for all trading strategies. A trading
    strategy is a set of rules that defines when to buy or sell an asset.

    Attributes:
        algorithm_id (string): the unique id for your
            combined strategy instances. An algorithm consists out of one or
            more strategy instances that run together. The algorithm_id
            is used to uniquely indentify the combined strategy instances.
            This is id is used in various places in the framework, e.g. for
            backtesting results, logging, monitoring etc.
        time_unit (TimeUnit): the time unit of the strategy that defines
            when the strategy should run e.g. HOUR, DAY, WEEK, MONTH
        interval (int): the interval of the strategy that defines how often
            the strategy should run within the time unit e.g. every 5 hours,
            every 2 days, every 3 weeks, every 4 months
        worker_id ((optional) str): the id of the worker
        strategy_id ((optional) str): the id of the strategy
        decorated ((optional) bool): the decorated function
        data_sources (List[DataSource] optional): the list of data
            sources to use for the strategy. The data sources will be used
            to indentify data providers that will be called to gather data
            and pass to the strategy before its run.
        metadata (optional): Dict[str, Any] - a dictionary
            containing metadata about the strategy. This can be used to
            store additional information about the strategy, such as its
            author, version, description, params etc.
    """
    algorithm_id: str
    time_unit: TimeUnit = None
    interval: int = None
    strategy_id: str = None
    decorated = None
    data_sources: List[DataSource] = []
    traces = None
    context: Context = None
    metadata: Dict[str, Any] = None
    position_sizes: List[PositionSize] = []
    stop_losses: List[StopLossRule] = []
    take_profits: List[TakeProfitRule] = []
    scaling_rules: List[ScalingRule] = []
    trading_costs: List[TradingCost] = []
    symbols: List[str] = []
    trading_symbol: str = None

    def __init__(
        self,
        algorithm_id=None,
        strategy_id=None,
        time_unit=None,
        interval=None,
        data_sources=None,
        metadata=None,
        position_sizes=None,
        stop_losses=None,
        take_profits=None,
        scaling_rules=None,
        trading_costs=None,
        symbols=None,
        trading_symbol=None,
        decorated=None
    ):
        if metadata is None:
            metadata = {}

        self.metadata = metadata

        if strategy_id is not None:
            self.strategy_id = strategy_id
        else:
            self.strategy_id = self.__class__.__name__

        # Initialize algorithm_id: use provided value, fall back to class
        # attribute if set, otherwise None
        if algorithm_id is not None:
            self.algorithm_id = algorithm_id
        elif "algorithm_id" in self.metadata:
            self.algorithm_id = self.metadata["algorithm_id"]
        else:
            # Check if class has algorithm_id defined as an actual value
            # (not just a type hint). Type hints result in the type being
            # returned (e.g., str, int), so we check for that.
            class_algorithm_id = getattr(self.__class__, 'algorithm_id', None)

            # If it's a type (like str, int) or None, it's just a type hint
            # In that case, use the class name as the algorithm_id
            if (class_algorithm_id is None
                    or isinstance(class_algorithm_id, type)):
                self.algorithm_id = None
            else:
                self.algorithm_id = class_algorithm_id

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

        # Initialize data_sources as a new list per instance
        # to avoid sharing the class-level mutable default
        if data_sources is not None:
            self.data_sources = list(data_sources)
        else:
            # Check if class has data_sources defined, copy them
            class_data_sources = getattr(self.__class__, 'data_sources', [])
            self.data_sources = list(class_data_sources) \
                if class_data_sources else []

        if decorated is not None:
            self.decorated = decorated

        # Initialize position_sizes as a new list per instance
        if position_sizes is not None:
            self.position_sizes = list(position_sizes)
        else:
            class_position_sizes = getattr(
                self.__class__, 'position_sizes', []
            )
            self.position_sizes = list(class_position_sizes) \
                if class_position_sizes else []

        # Initialize symbols as a new list per instance
        if symbols is not None:
            self.symbols = list(symbols)
        else:
            class_symbols = getattr(self.__class__, 'symbols', [])
            self.symbols = list(class_symbols) if class_symbols else []

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol

        # Check if interval is None
        if self.interval is None:
            raise OperationalException(
                f"Interval not set for strategy instance {self.strategy_id}"
            )

        # Check if scheduling interval is faster than the smallest
        # OHLCV data source timeframe
        ohlcv_timeframes = [
            ds.time_frame.amount_of_minutes
            for ds in self.data_sources
            if ds.time_frame is not None
            and DataType.OHLCV.equals(ds.data_type)
        ]

        if ohlcv_timeframes:
            scheduling_interval = \
                self.time_unit.amount_of_minutes * self.interval
            smallest_timeframe = min(ohlcv_timeframes)

            if scheduling_interval < smallest_timeframe:
                raise OperationalException(
                    f"Strategy '{self.strategy_id}' scheduling interval "
                    f"({self.interval} {self.time_unit.value.lower()}"
                    f"{'s' if self.interval > 1 else ''}"
                    f" = {scheduling_interval} min) is faster than "
                    f"the smallest OHLCV data source timeframe "
                    f"({smallest_timeframe} min). The strategy would "
                    f"run without new data. Increase the scheduling "
                    f"interval or use a smaller data timeframe."
                )

        # Initialize stop_losses as a new list per instance
        if stop_losses is not None:
            self.stop_losses = list(stop_losses)
        else:
            class_stop_losses = getattr(self.__class__, 'stop_losses', [])
            self.stop_losses = list(class_stop_losses) \
                if class_stop_losses else []

        # Initialize take_profits as a new list per instance
        if take_profits is not None:
            self.take_profits = list(take_profits)
        else:
            class_take_profits = getattr(self.__class__, 'take_profits', [])
            self.take_profits = list(class_take_profits) \
                if class_take_profits else []

        # Initialize scaling_rules as a new list per instance
        if scaling_rules is not None:
            self.scaling_rules = list(scaling_rules)
        else:
            class_scaling_rules = getattr(
                self.__class__, 'scaling_rules', []
            )
            self.scaling_rules = list(class_scaling_rules) \
                if class_scaling_rules else []

        # Initialize trading_costs as a new list per instance
        if trading_costs is not None:
            self.trading_costs = list(trading_costs)
        else:
            class_trading_costs = getattr(
                self.__class__, 'trading_costs', []
            )
            self.trading_costs = list(class_trading_costs) \
                if class_trading_costs else []

        # context initialization
        self._context = None
        self._last_run = None
        self.stop_loss_rules_lookup = {}
        self.take_profit_rules_lookup = {}
        self.scaling_rules_lookup = {}
        self.position_sizes_lookup = {}
        self._parameters = {}

        # Scaling state: tracks cooldown and scale-out count per symbol.
        # Persists across run_strategy() calls in event-based backtests.
        self._cooldown_remaining = {}   # {symbol: bars remaining}
        self._scale_out_counts = {}     # {symbol: number of scale-outs}

    def set_parameters(self, params: dict) -> None:
        """
        Store strategy parameters for saving alongside backtest results.
        Only JSON-serializable values (str, int, float, bool, None, list,
        dict) are kept; non-serializable values are silently dropped.

        Args:
            params (dict): A dictionary of parameter names to values.
        """
        _JSON_TYPES = (str, int, float, bool, type(None))

        def _is_serializable(v):
            if isinstance(v, _JSON_TYPES):
                return True
            if isinstance(v, (list, tuple)):
                return all(_is_serializable(x) for x in v)
            if isinstance(v, dict):
                return all(
                    isinstance(k, str) and _is_serializable(val)
                    for k, val in v.items()
                )
            return False

        self._parameters = {
            k: v for k, v in params.items() if _is_serializable(v)
        }

    def get_parameters(self) -> dict:
        """
        Return the stored strategy parameters.

        Returns:
            dict: The strategy parameters dictionary.
        """
        return dict(self._parameters)

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
                the buy signals. The series must be a pandas Series with
                a boolean value for each row in the data source, e.g.
                pd.Series([True, False, False, True, ...], index=data.index)
                Also the return dictionary must look like:
                {
                    "BTC": pd.Series([...]),
                    "ETH": pd.Series([...]),
                    ...
                }
                where the symbols are exactly the same as defined in the
                symbols attribute of the strategy.
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
            data (Dict[str, Any]): All the data that is defined in the
                data sources of the strategy. E.g. if there is a data source
                defined as DataSource(identifier="bitvavo_btc_eur_1h",
                symbol="BTC/EUR", time_frame="1h", data_type=DataType.OHLCV,
                window_size=100, market="BITVAVO"), the data dictionary
                will contain a key "bitvavo_btc_eur_1h"
                with the corresponding data as a polars DataFrame.

        Returns:
            Dict[str, Series]: A dictionary where the keys are the
                symbols and the values are pandas Series containing
                the sell signals. The series must be a pandas Series with
                a boolean value for each row in the data source, e.g.
                pd.Series([True, False, False, True, ...], index=data.index)
                Also the return dictionary must look like:
                {
                    "BTC": pd.Series([...]),
                    "ETH": pd.Series([...]),
                    ...
                }
                where the symbols are exactly the same as defined in the
                symbols attribute of the strategy.
        """
        raise NotImplementedError(
            "generate_sell_signals method not implemented"
        )

    def run_strategy(self, context: Context, data: Dict[str, Any]):
        """
        Main function for running the strategy. This function will be called
        by the framework when the trigger of your strategy is met.

        The flow of this function is as follows:
        1. Loop through all the symbols defined in the strategy.
        2. For each symbol, check if there are any open orders.
            A. If there are open orders, skip to the next symbol.
        3. If there is no open position, generate buy signals
            A. Generate buy signals
            B. If there is a buy signal, retrieve the position size
                defined for the symbol.
            C. If there is a take profit or stop loss rule defined
                for the symbol, register them for the trade that
                has been created as part of the order execution.
        4. If there is an open position, generate sell signals
            A. Generate sell signals
            B. If there is a sell signal, create a limit order to
                sell the position.

        During execution of this function, the context and market data
        will be passed to the function. The context is an instance of
        the Context class, this class has various methods to do operations
        with your portfolio, orders, trades, positions and other components.

        The market data is a dictionary containing all the data retrieved
        from the specified data sources.

        When buy or sell signals are generated, the strategy will create
        limit orders to buy or sell the assets based on the generated signals.
        For each symbol a corresponding position size must be defined. If
        no position size is defined, an OperationalException will be raised.

        Before creating new orders, the strategy will check if there are any
        stop losses or take profits for symbol registered. It will
        use the function get_stop_losses and get_take_profits, these functions
        can be overridden by the user to provide custom stop losses and
        take profits logic. The default functions will return the stop losses
        and take profits that are registered for the symbol if any.

        Args:
            context (Context): The context of the strategy. This is an instance
                of the Context class, this class has various methods to do
                operations with your portfolio, orders, trades, positions and
                other components.
            data (Dict[str, Any]): The data for the strategy.
                This is a dictionary containing all the data retrieved from the
                specified data sources. The keys are either the
                identifiers of the data sources or a generated key, usually
                <target_symbol>_<trading_symbol>_<time_frame> e.g. BTC-EUR_1h.

        Returns:
            None
        """
        self.context = context
        index_datetime = context.config[INDEX_DATETIME]
        buy_signals = self.generate_buy_signals(data)
        sell_signals = self.generate_sell_signals(data)

        # Generate optional scale-in/scale-out signals.
        # If generate_scale_in_signals returns None, fall back to buy_signals.
        # If generate_scale_out_signals returns None, no scale-out occurs.
        scale_in_signals = self.generate_scale_in_signals(data)
        scale_out_signals = self.generate_scale_out_signals(data)

        if scale_in_signals is None:
            scale_in_signals = buy_signals

        # Tick down cooldown counters for all symbols
        for symbol in self.symbols:
            if symbol in self._cooldown_remaining:
                self._cooldown_remaining[symbol] -= 1
                if self._cooldown_remaining[symbol] <= 0:
                    del self._cooldown_remaining[symbol]

        # Phase 1: Collect all pending buy orders (new entries + scale-ins)
        pending_buy_orders = []
        portfolio = self.context.get_portfolio()
        available_funds = self.context.get_unallocated()

        for symbol in self.symbols:

            if self.has_open_orders(symbol):
                continue

            # Check cooldown — skip buy/scale-in if in cooldown
            if symbol in self._cooldown_remaining:
                continue

            if not self.has_position(symbol):
                # --- New entry ---
                if symbol not in buy_signals:
                    continue

                signals = buy_signals[symbol]
                last_row = signals.iloc[-1]

                if last_row:
                    position_size = self.get_position_size(symbol)
                    full_symbol = (f"{symbol}/"
                                   f"{self.context.get_trading_symbol()}")
                    price = self.context.get_latest_price(full_symbol)
                    amount = position_size.get_size(portfolio, price)

                    pending_buy_orders.append({
                        'symbol': symbol,
                        'full_symbol': full_symbol,
                        'price': price,
                        'amount': amount,
                    })
            else:
                # --- Scale-in: add to existing position ---
                scaling_rule = self.get_scaling_rule(symbol)

                if scaling_rule is None:
                    continue

                if symbol not in scale_in_signals:
                    continue

                signals = scale_in_signals[symbol]
                last_row = signals.iloc[-1]

                if not last_row:
                    continue

                # Check max_entries: count open trades for this symbol
                open_trades = self.context.get_open_trades(
                    target_symbol=symbol
                )
                num_entries = len(open_trades)

                if num_entries >= scaling_rule.max_entries:
                    logger.info(
                        f"Skipping scale-in for {symbol}: "
                        f"max entries reached "
                        f"({num_entries}/{scaling_rule.max_entries})"
                    )
                    continue

                # Check max_position_percentage cap
                if scaling_rule.max_position_percentage is not None:
                    current_pct = \
                        self.context \
                        .get_position_percentage_of_portfolio_by_net_size(
                            symbol
                        )

                    if current_pct >= scaling_rule.max_position_percentage:
                        logger.info(
                            f"Skipping scale-in for {symbol}: "
                            f"position is {current_pct:.1f}% of portfolio, "
                            f"cap is "
                            f"{scaling_rule.max_position_percentage}%"
                        )
                        continue

                # Use per-entry percentage (0-indexed: entry 0 = first
                # scale-in after the initial buy)
                scale_in_index = num_entries - 1
                pct = scaling_rule.get_scale_in_percentage(scale_in_index)

                position_size = self.get_position_size(symbol)
                full_symbol = (f"{symbol}/"
                               f"{self.context.get_trading_symbol()}")
                price = self.context.get_latest_price(full_symbol)
                base_amount = position_size.get_size(portfolio, price)
                amount = base_amount * (pct / 100)

                # Clamp to max_position_percentage if set
                if scaling_rule.max_position_percentage is not None:
                    net_size = portfolio.get_net_size()
                    max_allowed = (
                        net_size
                        * scaling_rule.max_position_percentage / 100
                    )
                    position = self.get_position(symbol)
                    current_cost = position.cost if position else 0
                    headroom = max_allowed - current_cost

                    if headroom <= 0:
                        continue

                    amount = min(amount, headroom)

                pending_buy_orders.append({
                    'symbol': symbol,
                    'full_symbol': full_symbol,
                    'price': price,
                    'amount': amount,
                })

        # Phase 2: Scale orders proportionally if total exceeds available
        total_required = sum(o['amount'] for o in pending_buy_orders)

        if total_required > available_funds and total_required > 0:
            scale_factor = available_funds / total_required
            logger.warning(
                f"Total allocation ({total_required:.2f}) exceeds available "
                f"funds ({available_funds:.2f}). Scaling all orders by "
                f"{scale_factor:.2%} to maintain proportional allocation."
            )
            for order in pending_buy_orders:
                order['amount'] *= scale_factor

        # Phase 3: Execute all pending buy orders
        for order_data in pending_buy_orders:
            symbol = order_data['symbol']
            amount = order_data['amount']
            price = order_data['price']

            # Skip if amount is too small after scaling
            if amount <= 0.01:
                logger.warning(
                    f"Skipping buy order for {symbol}: "
                    f"amount too small after scaling ({amount:.4f})"
                )
                continue

            order_amount = amount / price
            order = self.create_limit_order(
                target_symbol=symbol,
                order_side=OrderSide.BUY,
                amount=order_amount,
                price=price,
                execute=True,
                validate=True,
                sync=True,
                metadata={"order_reason": "buy_signal"}
            )

            # Retrieve and apply stop loss and take profit rules
            stop_loss_rule = self.get_stop_loss_rule(symbol)
            take_profit_rule = self.get_take_profit_rule(symbol)

            if stop_loss_rule is not None:
                trade = self.context.get_trade(order_id=order.id)
                self.context.add_stop_loss(
                    trade=trade,
                    percentage=stop_loss_rule.percentage_threshold,
                    trailing=stop_loss_rule.trailing,
                    sell_percentage=stop_loss_rule.sell_percentage,
                    created_at=index_datetime
                )

            if take_profit_rule is not None:
                trade = self.context.get_trade(order_id=order.id)
                self.context.add_take_profit(
                    trade=trade,
                    percentage=take_profit_rule.percentage_threshold,
                    trailing=take_profit_rule.trailing,
                    sell_percentage=take_profit_rule.sell_percentage,
                    created_at=index_datetime
                )

            # Start cooldown after a buy/scale-in
            scaling_rule = self.get_scaling_rule(symbol)
            if scaling_rule and scaling_rule.cooldown_in_bars > 0:
                self._cooldown_remaining[symbol] = \
                    scaling_rule.cooldown_in_bars

        # Phase 4: Process sell and scale-out signals.
        # Sell (full exit) ALWAYS takes priority over scale-out.
        for symbol in self.symbols:

            if self.has_open_orders(symbol):
                continue

            if not self.has_position(symbol):
                continue

            # Check cooldown — skip sell/scale-out if in cooldown
            if symbol in self._cooldown_remaining:
                continue

            # Phase 4a: Full sell (always checked first — bypasses scaling)
            if symbol in sell_signals:
                signals = sell_signals[symbol]
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
                        price=price,
                        metadata={"order_reason": "sell_signal"}
                    )

                    # Reset scale-out counter and start cooldown
                    self._scale_out_counts.pop(symbol, None)
                    scaling_rule = self.get_scaling_rule(symbol)
                    if scaling_rule and scaling_rule.cooldown_in_bars > 0:
                        self._cooldown_remaining[symbol] = \
                            scaling_rule.cooldown_in_bars

                    continue

            # Phase 4b: Scale-out (partial close)
            scaling_rule = self.get_scaling_rule(symbol)

            if (scaling_rule is not None
                    and scale_out_signals is not None
                    and symbol in scale_out_signals):
                signals = scale_out_signals[symbol]
                last_row = signals.iloc[-1]

                if last_row:
                    position = self.get_position(symbol)

                    if position is not None and position.amount > 0:
                        so_index = self._scale_out_counts.get(symbol, 0)
                        pct = scaling_rule.get_scale_out_percentage(
                            so_index
                        )
                        sell_amount = position.amount * pct / 100

                        if sell_amount > 0.0:
                            full_symbol = (
                                f"{symbol}/"
                                f"{self.context.get_trading_symbol()}"
                            )
                            price = self.context.get_latest_price(
                                full_symbol
                            )
                            self.create_limit_order(
                                target_symbol=symbol,
                                order_side=OrderSide.SELL,
                                amount=sell_amount,
                                execute=True,
                                validate=True,
                                sync=True,
                                price=price,
                                metadata={"order_reason": "scale_out"}
                            )

                            self._scale_out_counts[symbol] = so_index + 1

                            # Start cooldown after a scale-out
                            if scaling_rule.cooldown_in_bars > 0:
                                self._cooldown_remaining[symbol] = \
                                    scaling_rule.cooldown_in_bars

    def apply_strategy(self, context, data):
        if self.decorated:
            self.decorated(context=context, data=data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.strategy_id,
            interval=self.interval,
            time_unit=self.time_unit,
            data_sources=self.data_sources
        )

    def get_take_profit_rule(self, symbol: str) -> Union[TakeProfitRule, None]:
        """
        Get the take profit definition for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[TakeProfitRule, None]: The take profit rule if found,
              None otherwise.
        """

        if self.take_profits is None or len(self.take_profits) == 0:
            return None

        if self.take_profit_rules_lookup == {}:
            for tp in self.take_profits:
                self.take_profit_rules_lookup[tp.symbol] = tp

        return self.take_profit_rules_lookup.get(symbol, None)

    def get_stop_loss_rule(self, symbol: str) -> Union[StopLossRule, None]:
        """
        Get the stop loss definition for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[StopLossRule, None]: The stop loss rule if found,
              None otherwise.
        """

        if self.stop_losses is None or len(self.stop_losses) == 0:
            return None

        if self.stop_loss_rules_lookup == {}:
            for sl in self.stop_losses:
                self.stop_loss_rules_lookup[sl.symbol] = sl

        return self.stop_loss_rules_lookup.get(symbol, None)

    def get_position_size(self, symbol: str) -> Union[PositionSize, None]:
        """
        Get the position size definition for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[PositionSize, None]: The position size if found,
              None otherwise.
        """

        if self.position_sizes is not None and len(self.position_sizes) == 0:
            raise OperationalException(
                f"No position size defined for symbol "
                f"{symbol} in strategy "
                f"{self.strategy_id}"
            )

        if self.position_sizes_lookup == {}:
            for ps in self.position_sizes:
                self.position_sizes_lookup[ps.symbol] = ps

        position_size = self.position_sizes_lookup.get(symbol, None)

        if position_size is None:
            raise OperationalException(
                f"No position size defined for symbol "
                f"{symbol} in strategy "
                f"{self.strategy_id}"
            )

        return position_size

    def get_scaling_rule(self, symbol: str) -> Union[ScalingRule, None]:
        """
        Get the scaling rule for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[ScalingRule, None]: The scaling rule if found,
              None otherwise.
        """

        if self.scaling_rules is None or len(self.scaling_rules) == 0:
            return None

        if self.scaling_rules_lookup == {}:
            for sr in self.scaling_rules:
                self.scaling_rules_lookup[sr.symbol] = sr

        return self.scaling_rules_lookup.get(symbol, None)

    def generate_scale_in_signals(
        self, data: Dict[str, Any]
    ) -> Union[Dict[str, pd.Series], None]:
        """
        Optional method to generate scale-in signals. Override this to
        provide separate logic for when to add to an existing position.

        If not overridden, the framework falls back to using
        generate_buy_signals for scale-in decisions.

        Args:
            data (Dict[str, Any]): The market data for the strategy.

        Returns:
            Dict[str, Series] | None: A dictionary where the keys are
                symbols and values are pandas Series with boolean
                scale-in signals per row. Return None to fall back
                to buy signals.
        """
        return None

    def generate_scale_out_signals(
        self, data: Dict[str, Any]
    ) -> Union[Dict[str, pd.Series], None]:
        """
        Optional method to generate scale-out signals. Override this to
        provide separate logic for when to partially close a position.

        If not overridden, no scale-out signals are generated (only
        full sell signals from generate_sell_signals apply).

        Args:
            data (Dict[str, Any]): The market data for the strategy.

        Returns:
            Dict[str, Series] | None: A dictionary where the keys are
                symbols and values are pandas Series with boolean
                scale-out signals per row. Return None for no
                scale-out signals.
        """
        return None

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
        sync=True,
        metadata=None
    ) -> Order:
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
        return self.context.create_limit_order(
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
            sync=sync,
            metadata=metadata
        )

    def create_market_order(
        self,
        target_symbol,
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
        sync=True,
        metadata=None
    ) -> Order:
        """
        Function to create a market order. Market orders execute at
        the best available price. In backtesting, this means the
        open price of the next candle (+ slippage).

        Args:
            target_symbol: The symbol of the asset to trade
            order_side: The side of the order (BUY or SELL)
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
            metadata (optional): Additional metadata for the order

        Returns:
            Order: Instance of the order created
        """
        return self.context.create_market_order(
            target_symbol=target_symbol,
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
            sync=sync,
            metadata=metadata
        )

    def close_position(
        self, symbol, market=None, identifier=None, precision=None
    ) -> Order:
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
        return self.context.close_position(
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

    def get_data_sources(self):
        """
        Function to get the data sources of the strategy

        Returns:
            List[DataSource]: The data sources of the strategy
        """
        return self.data_sources

    def __repr__(self):
        return f"<TradingStrategy(strategy_id={self.strategy_id})>"
