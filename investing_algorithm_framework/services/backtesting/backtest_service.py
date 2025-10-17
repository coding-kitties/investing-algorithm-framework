import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Union
from uuid import uuid4

import numpy as np
import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import BacktestRun, OrderType, \
    TimeUnit, Trade, OperationalException, BacktestDateRange, TimeFrame, \
    Backtest, TradeStatus, PortfolioSnapshot, Order, OrderStatus, OrderSide, \
    Portfolio, DataType, generate_backtest_summary_metrics, \
    PortfolioConfiguration
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.portfolios import \
    PortfolioConfigurationService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics

logger = logging.getLogger(__name__)


class BacktestService:
    """
    Service that facilitates backtests for algorithm objects.
    """

    def __init__(
        self,
        data_provider_service: DataProviderService,
        order_service,
        portfolio_service,
        portfolio_snapshot_service,
        position_repository,
        trade_service,
        configuration_service,
        portfolio_configuration_service,
    ):
        super().__init__()
        self._order_service = order_service
        self._trade_service = trade_service
        self._portfolio_service = portfolio_service
        self._portfolio_snapshot_service = portfolio_snapshot_service
        self._position_repository = position_repository
        self._configuration_service = configuration_service
        self._portfolio_configuration_service: PortfolioConfigurationService \
            = portfolio_configuration_service
        self._data_provider_service = data_provider_service

    def validate_strategy_for_vector_backtest(self, strategy):
        """
        Validate if the strategy is suitable for backtesting.

        Args:
            strategy: The strategy to validate.

        Raises:
            OperationalException: If the strategy does not have the required
                buy/sell signal functions.
        """
        if not hasattr(strategy, 'generate_buy_signals'):
            raise OperationalException(
                "Strategy must define a vectorized buy signal function "
                "(buy_signal_vectorized)."
            )
        if not hasattr(strategy, 'generate_sell_signals'):
            raise OperationalException(
                "Strategy must define a vectorized sell signal function "
                "(sell_signal_vectorized)."
            )

    def _get_data_frame_index(self, data: Union[pl.DataFrame, pd.DataFrame]):
        """
        Function to return the index for a given df. If the provided
        data is of type pandas Dataframe, first will be checked if
        it has a index. If this is not the case the function will
        check if there is a 'DateTime' column and add this
        as the index.

        For a polars DataFrame, the 'DateTime' column will be
        used as the index if it exists.

        If no index is found an exception will be raised.

        Args:
            data: The data frame to process.

        Raises:
            OperationalException: If no valid index is found.

        Returns:
            The index of the data frame.
        """
        if isinstance(data, pl.DataFrame):
            if "Datetime" in data.columns:
                return data["Datetime"]
            else:
                raise OperationalException("No valid index found.")
        elif isinstance(data, pd.DataFrame):
            if data.index is not None:
                return data.index
            elif "Datetime" in data.columns:
                return data["Datetime"]
            else:
                raise OperationalException("No valid index found.")
        else:
            raise ValueError("Unsupported data frame type.")

    def create_vector_backtest(
        self,
        strategy,
        backtest_date_range: BacktestDateRange,
        risk_free_rate: float = 0.027,
        initial_amount: float = None,
        trading_symbol: str = None,
        market: str = None,
    ) -> BacktestRun:
        """
        Vectorized backtest for multiple assets using strategy
        buy/sell signals.

        Args:
            strategy: The strategy to backtest.
            backtest_date_range: The date range for the backtest.
            risk_free_rate: The risk-free rate to use for the backtest
                metrics. Default is 0.027 (2.7%).
            initial_amount: The initial amount to use for the backtest.
                If None, the initial amount will be taken from the first
                portfolio configuration.
            trading_symbol: The trading symbol to use for the backtest.
                If None, the trading symbol will be taken from the first
                portfolio configuration.
            market: The market to use for the backtest. If None, the market
                will be taken from the first portfolio configuration.

        Returns:
            BacktestRun: The backtest run containing the results and metrics.
        """
        portfolio_configurations = self._portfolio_configuration_service\
            .get_all()

        if (
                portfolio_configurations is None
                or len(portfolio_configurations) == 0
        ) and (
                initial_amount is None
                or trading_symbol is None
                or market is None
        ):
            raise OperationalException(
                "No initial amount, trading symbol or market provided "
                "for the backtest and no portfolio configurations found. "
                "please register a portfolio configuration "
                "or specify the initial amount, trading symbol and "
                "market parameters before running a backtest."
            )

        if portfolio_configurations is None \
                or len(portfolio_configurations) == 0:
            portfolio_configurations = []
            portfolio_configurations.append(
                PortfolioConfiguration(
                    identifier="vector_backtest",
                    market=market,
                    trading_symbol=trading_symbol,
                    initial_balance=initial_amount
                )
            )

        portfolio_configuration = portfolio_configurations[0]

        trading_symbol = portfolio_configurations[0].trading_symbol
        portfolio = Portfolio.from_portfolio_configuration(
            portfolio_configuration
        )

        # Load vectorized backtest data
        data = self._data_provider_service.get_vectorized_backtest_data(
            data_sources=strategy.data_sources,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date
        )

        # Compute signals from strategy
        buy_signals = strategy.generate_buy_signals(data)
        sell_signals = strategy.generate_sell_signals(data)

        # Build master index (union of all indices in signal dict)
        index = pd.Index([])

        most_granular_ohlcv_data_source = \
            BacktestService.get_most_granular_ohlcv_data_source(
                strategy.data_sources
            )
        most_granular_ohlcv_data = self._data_provider_service.get_ohlcv_data(
                symbol=most_granular_ohlcv_data_source.symbol,
                start_date=backtest_date_range.start_date,
                end_date=backtest_date_range.end_date,
                pandas=True
            )

        # Make sure to filter out the buy and sell signals that are before
        # the backtest start date
        buy_signals = {k: v[v.index >= backtest_date_range.start_date]
                       for k, v in buy_signals.items()}
        sell_signals = {k: v[v.index >= backtest_date_range.start_date]
                        for k, v in sell_signals.items()}

        index = index.union(most_granular_ohlcv_data.index)
        index = index.sort_values()

        # Initialize trades and portfolio values
        trades = []
        orders = []
        granular_ohlcv_data_order_by_symbol = {}
        snapshots = [
            PortfolioSnapshot(
                trading_symbol=trading_symbol,
                portfolio_id=portfolio.identifier,
                created_at=backtest_date_range.start_date,
                unallocated=initial_amount,
                total_value=initial_amount,
                total_net_gain=0.0
            )
        ]

        for symbol in buy_signals.keys():
            full_symbol = f"{symbol}/{trading_symbol}"
            # find PositionSize object
            pos_size_obj = next(
                (p for p in strategy.position_sizes if
                 p.symbol == symbol), None
            )
            # Load most granular OHLCV data for the symbol
            df = self._data_provider_service.get_ohlcv_data(
                symbol=full_symbol,
                start_date=backtest_date_range.start_date,
                end_date=backtest_date_range.end_date,
                pandas=True
            )
            granular_ohlcv_data_order_by_symbol[full_symbol] = df

            # Align signals with most granular OHLCV data
            close = df["Close"]
            buy_signal = buy_signals[symbol].reindex(index, fill_value=False)
            sell_signal = sell_signals[symbol].reindex(index, fill_value=False)

            signal = pd.Series(0, index=index)
            signal[buy_signal] = 1
            signal[sell_signal] = -1
            signal = signal.replace(0, np.nan).ffill().shift(1).fillna(0)
            signal = signal.astype(float)

            if pos_size_obj is None:
                raise OperationalException(
                    f"No position size object defined "
                    f"for symbol {symbol}, please make sure to "
                    f"register a PositionSize object in the strategy."
                )

            capital_for_trade = pos_size_obj.get_size(
                Portfolio(
                    unallocated=initial_amount,
                    initial_balance=initial_amount,
                    trading_symbol=trading_symbol,
                    net_size=0,
                    market="BACKTEST",
                    identifier="vector_backtest"
                ) if pos_size_obj else (initial_amount / len(buy_signals)),
                asset_price=close.iloc[0]
            )

            # Trade generation
            last_trade = None

            # Align signals with most granular OHLCV data
            close = df["Close"].reindex(index, method='ffill')
            buy_signal = buy_signals[symbol].reindex(index, fill_value=False)
            sell_signal = sell_signals[symbol].reindex(index, fill_value=False)

            # Loop over all timestamps in the backtest
            for i in range(len(index)):

                # 1 = buy, -1 = sell, 0 = hold
                current_signal = signal.iloc[i]
                current_price = float(close.iloc[i])
                current_date = index[i]

                # Convert the pd.Timestamp to an utc datetime object
                if isinstance(current_date, pd.Timestamp):
                    current_date = current_date.to_pydatetime()

                if current_date.tzinfo is None:
                    current_date = current_date.replace(tzinfo=timezone.utc)

                # If we are not in a position, and we get a buy signal
                if current_signal == 1 and last_trade is None:
                    amount = float(capital_for_trade / current_price)
                    buy_order = Order(
                        id=uuid4(),
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        order_type=OrderType.LIMIT,
                        price=current_price,
                        amount=amount,
                        status=OrderStatus.CLOSED,
                        created_at=current_date,
                        updated_at=current_date,
                        order_side=OrderSide.BUY
                    )
                    orders.append(buy_order)
                    trade = Trade(
                        id=uuid4(),
                        orders=[buy_order],
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        available_amount=amount,
                        remaining=0,
                        filled_amount=amount,
                        open_price=current_price,
                        opened_at=current_date,
                        closed_at=None,
                        amount=amount,
                        status=TradeStatus.OPEN.value,
                        cost=capital_for_trade
                    )
                    last_trade = trade
                    trades.append(trade)

                # If we are in a position, and we get a sell signal
                if current_signal == -1 and last_trade is not None:
                    net_gain_val = (
                        current_price - last_trade.open_price
                    ) * last_trade.available_amount
                    sell_order = Order(
                        id=uuid4(),
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        order_type=OrderType.LIMIT,
                        price=current_price,
                        amount=last_trade.available_amount,
                        status=OrderStatus.CLOSED,
                        created_at=current_date,
                        updated_at=current_date,
                        order_side=OrderSide.SELL
                    )
                    orders.append(sell_order)
                    trade_orders = last_trade.orders
                    trade_orders.append(sell_order)
                    last_trade.update(
                        {
                            "orders": trade_orders,
                            "closed_at": current_date,
                            "status": TradeStatus.CLOSED,
                            "updated_at": current_date,
                            "net_gain": net_gain_val
                        }
                    )
                    last_trade = None

        unallocated = initial_amount
        total_net_gain = 0.0
        open_trades = []

        # Create portfolio snapshots
        for ts in index:
            allocated = 0
            interval_datetime = pd.Timestamp(ts).to_pydatetime()
            interval_datetime = interval_datetime.replace(tzinfo=timezone.utc)

            for trade in trades:

                if trade.opened_at == interval_datetime:
                    # Snapshot taken at the moment a trade is opened
                    unallocated -= trade.cost
                    open_trades.append(trade)

                if trade.closed_at == interval_datetime:
                    # Snapshot taken at the moment a trade is closed
                    unallocated += trade.cost + trade.net_gain
                    total_net_gain += trade.net_gain
                    open_trades.remove(trade)

            for open_trade in open_trades:
                ohlcv = granular_ohlcv_data_order_by_symbol[
                    f"{open_trade.target_symbol}/{trading_symbol}"
                ]
                try:
                    price = ohlcv.loc[:ts, "Close"].iloc[-1]
                    open_trade.last_reported_price = price
                except IndexError:
                    continue  # skip if no price yet

                allocated += open_trade.filled_amount * price

            # total_value = invested_value + unallocated
            # total_net_gain = total_value - initial_amount
            snapshots.append(
                PortfolioSnapshot(
                    portfolio_id=portfolio.identifier,
                    created_at=interval_datetime,
                    unallocated=unallocated,
                    total_value=unallocated + allocated,
                    total_net_gain=total_net_gain
                )
            )

        unique_symbols = set()
        for trade in trades:
            unique_symbols.add(trade.target_symbol)

        number_of_trades_closed = len(
            [t for t in trades if TradeStatus.CLOSED.equals(t.status)]
        )
        number_of_trades_open = len(
            [t for t in trades if TradeStatus.OPEN.equals(t.status)]
        )
        # Create a backtest run object
        run = BacktestRun(
            trading_symbol=trading_symbol,
            initial_unallocated=initial_amount,
            number_of_runs=1,
            portfolio_snapshots=snapshots,
            trades=trades,
            orders=orders,
            positions=[],
            created_at=datetime.now(timezone.utc),
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            number_of_days=(
                backtest_date_range.end_date - backtest_date_range.end_date
            ).days,
            number_of_trades=len(trades),
            number_of_orders=len(orders),
            number_of_trades_closed=number_of_trades_closed,
            number_of_trades_open=number_of_trades_open,
            number_of_positions=len(unique_symbols),
            symbols=list(buy_signals.keys())
        )

        # Create backtest metrics
        run.backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        return run

    def generate_schedule(
        self,
        strategies,
        tasks,
        start_date,
        end_date
    ) -> Dict[datetime, Dict[str, List[str]]]:
        """
        Generates a dict-based schedule: datetime => {strategy_ids, task_ids}
        """
        schedule = defaultdict(
            lambda: {"strategy_ids": set(), "task_ids": set(tasks)}
        )

        for strategy in strategies:
            strategy_id = strategy.strategy_profile.strategy_id
            interval = strategy.strategy_profile.interval
            time_unit = strategy.strategy_profile.time_unit

            if time_unit == TimeUnit.SECOND:
                step = timedelta(seconds=interval)
            elif time_unit == TimeUnit.MINUTE:
                step = timedelta(minutes=interval)
            elif time_unit == TimeUnit.HOUR:
                step = timedelta(hours=interval)
            elif time_unit == TimeUnit.DAY:
                step = timedelta(days=interval)
            else:
                raise ValueError(f"Unsupported time unit: {time_unit}")

            t = start_date
            while t <= end_date:
                schedule[t]["strategy_ids"].add(strategy_id)
                t += step

        return {
            ts: {
                "strategy_ids": sorted(data["strategy_ids"]),
                "task_ids": sorted(data["task_ids"])
            }
            for ts, data in schedule.items()
        }

    def get_strategy_from_strategy_profiles(self, strategy_profiles, id):

        for strategy_profile in strategy_profiles:

            if strategy_profile.strategy_id == id:
                return strategy_profile

        raise ValueError(f"Strategy profile with id {id} not found.")

    def _get_initial_unallocated(self) -> float:
        """
        Get the initial unallocated amount for the backtest.

        Returns:
            float: The initial unallocated amount.
        """
        portfolios = self._portfolio_service.get_all()
        initial_unallocated = 0.0

        for portfolio in portfolios:
            initial_unallocated += portfolio.initial_balance

        return initial_unallocated

    def create_backtest(
        self,
        algorithm,
        number_of_runs,
        backtest_date_range: BacktestDateRange,
        risk_free_rate,
        strategy_directory_path=None
    ) -> Backtest:
        """
        Create a backtest for the given algorithm.

        It will store all results and metrics in a Backtest object through
        the BacktestResults and BacktestMetrics objects. Optionally,
        it will also store the strategy related paths and backtest
        data file paths.

        Args:
            algorithm: The algorithm to create the backtest report for
            number_of_runs: The number of runs
            backtest_date_range: The backtest date range of the backtest
            risk_free_rate: The risk-free rate to use for the backtest metrics
            strategy_directory_path (optional, str): The path to the
                strategy directory

        Returns:
            Backtest: The backtest containing the results and metrics.
        """

        # Get the first portfolio
        portfolio = self._portfolio_service.get_all()[0]

        # List all strategy related files in the strategy directory
        strategy_related_paths = []

        if strategy_directory_path is not None:
            if not os.path.exists(strategy_directory_path) or \
                    not os.path.isdir(strategy_directory_path):
                raise OperationalException(
                    "Strategy directory does not exist"
                )

            strategy_files = os.listdir(strategy_directory_path)
            for file in strategy_files:
                source_file = os.path.join(strategy_directory_path, file)
                if os.path.isfile(source_file):
                    strategy_related_paths.append(source_file)
        else:
            if algorithm is not None and hasattr(algorithm, 'strategies'):
                for strategy in algorithm.strategies:
                    mod = sys.modules[strategy.__module__]
                    strategy_directory_path = os.path.dirname(mod.__file__)
                    strategy_files = os.listdir(strategy_directory_path)
                    for file in strategy_files:
                        source_file = os.path.join(
                            strategy_directory_path, file
                        )
                        if os.path.isfile(source_file):
                            strategy_related_paths.append(source_file)

        run = BacktestRun(
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            initial_unallocated=self._get_initial_unallocated(),
            trading_symbol=portfolio.trading_symbol,
            created_at=datetime.now(tz=timezone.utc),
            portfolio_snapshots=self._portfolio_snapshot_service.get_all(
                {"portfolio_id": portfolio.id}
            ),
            number_of_runs=number_of_runs,
            trades=self._trade_service.get_all(
                {"portfolio": portfolio.id}
            ),
            orders=self._order_service.get_all(
                {"portfolio": portfolio.id}
            ),
            positions=self._position_repository.get_all(
                {"portfolio": portfolio.id}
            ),
        )
        backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        run.backtest_metrics = backtest_metrics
        return Backtest(
            backtest_runs=[run],
            backtest_summary=generate_backtest_summary_metrics(
                [backtest_metrics]
            )
        )

    @staticmethod
    def get_most_granular_ohlcv_data_source(data_sources):
        """
        Get the most granular data source from a list of data sources.

        Args:
            data_sources: List of data sources.

        Returns:
            The most granular data source.
        """
        granularity_order = {
            TimeFrame.ONE_MINUTE: 1,
            TimeFrame.FIVE_MINUTE: 5,
            TimeFrame.FIFTEEN_MINUTE: 15,
            TimeFrame.ONE_HOUR: 60,
            TimeFrame.TWO_HOUR: 120,
            TimeFrame.FOUR_HOUR: 240,
            TimeFrame.TWELVE_HOUR: 720,
            TimeFrame.ONE_DAY: 1440,
            TimeFrame.ONE_WEEK: 10080,
            TimeFrame.ONE_MONTH: 43200
        }

        most_granular = None
        highest_granularity = float('inf')

        ohlcv_data_sources = [
            ds for ds in data_sources if DataType.OHLCV.equals(ds.data_type)
        ]

        if len(ohlcv_data_sources) == 0:
            raise OperationalException("No OHLCV data sources found")

        for source in ohlcv_data_sources:

            if granularity_order[source.time_frame] < highest_granularity:
                highest_granularity = granularity_order[source.time_frame]
                most_granular = source

        return most_granular
