import gc
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Union, Tuple, Optional, Callable
from uuid import uuid4

import numpy as np
import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import BacktestRun, OrderType, \
    TimeUnit, Trade, OperationalException, BacktestDateRange, TimeFrame, \
    Backtest, TradeStatus, PortfolioSnapshot, Order, OrderStatus, OrderSide, \
    Portfolio, DataType, generate_backtest_summary_metrics, DataSource, \
    PortfolioConfiguration, tqdm, SnapshotInterval, combine_backtests, \
    save_backtests_to_directory
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics
from investing_algorithm_framework.services.metrics import \
    get_risk_free_rate_us
from investing_algorithm_framework.services.portfolios import \
    PortfolioConfigurationService

logger = logging.getLogger(__name__)
# Green color similar to tqdm progress bar
GREEN_COLOR = "\033[92m"
COLOR_RESET = "\033[0m"


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
            algorithm_id=algorithm.id,
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

    def backtest_exists(
        self,
        strategy,
        backtest_date_range: BacktestDateRange,
        storage_directory: str
    ) -> bool:
        """
        Check if a backtest already exists for the given strategy
        and backtest date range.

        Args:
            strategy: The strategy to check.
            backtest_date_range: The backtest date range to check.
            storage_directory: The directory where backtests are stored.

        Returns:
            bool: True if the backtest exists, False otherwise.
        """
        algorithm_id = strategy.algorithm_id
        backtest_directory = os.path.join(storage_directory, algorithm_id)

        if os.path.exists(backtest_directory):
            backtest = Backtest.open(backtest_directory)
            backtest_date_ranges = backtest.get_backtest_date_ranges()

            for backtest_date_range_ref in backtest_date_ranges:

                if backtest_date_range_ref.start_date \
                        == backtest_date_range.start_date and \
                        backtest_date_range_ref.end_date \
                        == backtest_date_range.end_date:
                    return True

        return False

    def load_backtest_by_strategy_and_backtest_date_range(
        self,
        strategy,
        backtest_date_range: BacktestDateRange,
        storage_directory: str
    ) -> Backtest:
        """
        Load a backtest for the given strategy and backtest date range.
        If the backtest does not exist, an exception will be raised.
        For the given backtest, only the run and metrics corresponding
        to the backtest date range will be returned.

        Args:
            strategy: The strategy to load the backtest for.
            backtest_date_range: The backtest date range to load.
            storage_directory: The directory where backtests are stored.

        Returns:
            Backtest: instance of the loaded backtest with only
                the given run and metrics corresponding to the
                backtest date range.
        """
        strategy_id = strategy.id
        backtest_directory = os.path.join(storage_directory, strategy_id)

        if os.path.exists(backtest_directory):
            backtest = Backtest.open(backtest_directory)
            run = backtest.get_backtest_run(backtest_date_range)
            metadata = backtest.get_metadata()
            return Backtest(backtest_runs=[run], metadata=metadata)
        else:
            raise OperationalException("Backtest does not exist.")

    def load_checkpoints(
        self,
        algorithm_ids: List[str],
        backtest_date_range: BacktestDateRange,
        backtest_storage_directory: str
    ) -> Tuple[List[Backtest], List[str]]:
        """
        Load backtest checkpoints for the given strategy IDs and
        backtest date range.

        Args:
            algorithm_ids: List of algorithm IDs to load checkpoints for.
            backtest_date_range: The backtest date range to load.
            backtest_storage_directory: The directory where backtests
                are stored.

        Returns:
            Tuple[List[Backtest], List[str]]: A tuple containing a list of
                loaded backtests and a list of strategy IDs for which no
                checkpoint was found.
        """
        loaded_backtests = []
        missing_strategy_ids = []

        for algorithm_id in algorithm_ids:
            backtest_directory = os.path.join(
                backtest_storage_directory, algorithm_id
            )

            if os.path.exists(backtest_directory):
                backtest = Backtest.open(backtest_directory)
                run = backtest.get_backtest_run(backtest_date_range)

                if run is None:
                    missing_strategy_ids.append(algorithm_id)
                    continue

                algorithm_id = backtest.algorithm_id
                metadata = backtest.get_metadata()
                loaded_backtests.append(
                    Backtest(
                        backtest_runs=[run],
                        metadata=metadata,
                        algorithm_id=algorithm_id
                    )
                )
            else:
                missing_strategy_ids.append(algorithm_id)

        return loaded_backtests, missing_strategy_ids

    def initialize_data_sources_backtest(
        self,
        data_sources: List[DataSource],
        backtest_date_range: BacktestDateRange,
        show_progress: bool = True
    ):
        """
        Function to initialize the data sources for the app in backtest mode.
        This method should be called before running the algorithm in backtest
        mode. It initializes all data sources so that they are
        ready to be used.

        Args:
            data_sources (List[DataSource]): The data sources to initialize.
            backtest_date_range (BacktestDateRange): The date range for the
                backtest. This should be an instance of BacktestDateRange.
            show_progress (bool): Whether to show a progress bar when
                preparing the backtest data for each data provider.

        Returns:
            None
        """
        logger.info("Initializing data sources for backtest")

        if data_sources is None or len(data_sources) == 0:
            return

        # Initialize all data sources
        self._data_provider_service.index_backtest_data_providers(
            data_sources, backtest_date_range, show_progress=show_progress
        )

        description = "Preparing backtest data for all data sources"
        data_providers = self._data_provider_service\
            .data_provider_index.get_all()

        # Prepare the backtest data for each data provider
        if not show_progress:
            for _, data_provider in data_providers:

                data_provider.prepare_backtest_data(
                    backtest_start_date=backtest_date_range.start_date,
                    backtest_end_date=backtest_date_range.end_date
                )
        else:
            for _, data_provider in tqdm(
                data_providers, desc=description, colour="green"
            ):
                data_provider.prepare_backtest_data(
                    backtest_start_date=backtest_date_range.start_date,
                    backtest_end_date=backtest_date_range.end_date
                )

    def run_vector_backtests_with_checkpoints(
        self,
        initial_amount,
        strategies: List,
        backtest_date_range: BacktestDateRange = None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        risk_free_rate: Optional[float] = None,
        skip_data_sources_initialization: bool = False,
        show_progress: bool = True,
        market: Optional[str] = None,
        trading_symbol: Optional[str] = None,
        continue_on_error: bool = False,
        window_filter_function: Optional[
            Callable[[List[Backtest], BacktestDateRange], List[Backtest]]
        ] = None,
        final_filter_function: Optional[
            Callable[[List[Backtest]], List[Backtest]]
        ] = None,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
    ):
        """
        Run vectorized backtests for multiple strategies with checkpointing.
        Args:
            strategies: List of strategies to backtest.
            backtest_storage_directory: Directory to store backtests.
            risk_free_rate: Risk-free rate for backtest metrics.
            backtest_date_range: Single backtest date range to use
                for all strategies.
            backtest_date_ranges (List[BacktestDateRange]): List of backtes
                date ranges to use for all strategies.
            skip_data_sources_initialization (bool): Whether to skip the
                initialization of data sources.
            show_progress (bool): Whether to show a progress bar and
                debug for the different processing steps.
            window_filter_function (
                Optional[Callable[[List[Backtest], BacktestDateRange],
                List[Backtest]]]
            ):
                A function that takes a list of Backtest objects and
                the current BacktestDateRange, and returns a filtered
                list of Backtest objects. This is applied after each
                backtest date range when backtest_date_ranges
                is provided. Only the strategies from the filtered
                backtests will continue to the next date range. This allows
                for progressive filtering
                of strategies based on their performance in previous periods.

                The function signature should be:
                    def filter_function(
                        backtests: List[Backtest],
                        backtest_date_range: BacktestDateRange
                    ) -> List[Backtest]
            final_filter_function (
                Optional[Callable[[List[Backtest]], List[Backtest]]]
            ):
                A function that takes a list of Backtest objects and
                returns a filtered list of Backtest objects. This is applied
                after all backtest date ranges have been processed when
                backtest_date_ranges is provided. Only the strategies from
                the filtered backtests will be returned as the final result.
                This allows for final filtering of strategies based on
                their overall performance across all periods. The function
                signature should be:
                    def filter_function(
                        backtests: List[Backtest]
                    ) -> List[Backtest]
        Returns:
            None
        """
        data_sources = []

        for strategy in strategies:
            data_sources.extend(strategy.data_sources)

        if risk_free_rate is None:

            if show_progress:
                print(
                    GREEN_COLOR +
                    "Retrieving risk free rate for metrics calculation ..." +
                    COLOR_RESET
                )
            risk_free_rate = get_risk_free_rate_us()

            if show_progress:
                print(
                    GREEN_COLOR,
                    f"Retrieving risk free rate of: {risk_free_rate}" +
                    COLOR_RESET
                )

        if backtest_date_range is None and backtest_date_ranges is None:
            raise OperationalException(
                "Either backtest_date_range or backtest_date_ranges must be "
                "provided"
            )

        # Run backtests for a single date range
        if backtest_date_range is not None:

            if not skip_data_sources_initialization:
                self.initialize_data_sources_backtest(
                    data_sources,
                    backtest_date_range,
                    show_progress=show_progress
                )

            algorithms_ids = [
                strategy.algorithm_id for strategy in strategies
            ]

            if show_progress:
                print(
                    GREEN_COLOR +
                    "Checking for checkpoints for "
                    f"backtest range: {backtest_date_range}" +
                    COLOR_RESET
                )

            backtests, missing = self.load_checkpoints(
                algorithms_ids,
                backtest_date_range,
                backtest_storage_directory
            )

            if show_progress:
                print(
                    GREEN_COLOR +
                    f"Found {len(backtests)} checkpoints" +
                    COLOR_RESET
                )

            strategies = [
                strategy for strategy in strategies
                if strategy.algorithm_id in missing
            ]
            missing_backtests = []

            for strategy in tqdm(
                strategies,
                    colour="green",
                    desc=f"{GREEN_COLOR}Running backtests{COLOR_RESET}"
            ):
                missing_backtests.append(
                    self.run_vector_backtest(
                        backtest_date_range=backtest_date_range,
                        initial_amount=initial_amount,
                        strategy=strategy,
                        snapshot_interval=snapshot_interval,
                        risk_free_rate=risk_free_rate,
                        skip_data_sources_initialization=True,
                        market=market,
                        trading_symbol=trading_symbol,
                        continue_on_error=continue_on_error,
                        backtest_storage_directory=backtest_storage_directory,
                        show_progress=False,
                    )
                )

            backtests.extend(missing_backtests)

            # Apply window filter function if set
            if window_filter_function is not None:
                backtests = window_filter_function(
                    backtests, backtest_date_range
                )

            # Apply final filter function if set
            if final_filter_function is not None:
                backtests = final_filter_function(backtests)

            backtests_to_be_saved = [
                bt for bt in missing_backtests if bt in backtests
            ]

            if show_progress:
                print(
                    GREEN_COLOR +
                    f"Saving {len(backtests_to_be_saved)} "
                    "backtests to storage ..." +
                    COLOR_RESET
                )

            save_backtests_to_directory(
                backtests=backtests_to_be_saved,
                directory_path=backtest_storage_directory,
            )
            return backtests
        else:
            backtests_ordered_by_algorithm = {}
            active_strategies = strategies.copy()
            active_algorithm_ids = [
                strategy.algorithm_id for strategy in active_strategies
            ]

            # Make sure that the backtest date ranges are
            # sorted by start date and are unique
            unique_date_ranges = set(backtest_date_ranges)
            backtest_date_ranges = sorted(
                unique_date_ranges, key=lambda x: x.start_date
            )

            for backtest_date_range in tqdm(
                backtest_date_ranges,
                colour="green",
                desc=f"{GREEN_COLOR}Running backtests for "
                     f"all date ranges{COLOR_RESET}"
            ):
                if not skip_data_sources_initialization:
                    self.initialize_data_sources_backtest(
                        data_sources,
                        backtest_date_range,
                        show_progress=show_progress
                    )

                start_date = backtest_date_range \
                    .start_date.strftime('%Y-%m-%d')
                end_date = backtest_date_range.end_date.strftime('%Y-%m-%d')

                if show_progress:
                    # Green color similar to tqdm
                    print(
                        GREEN_COLOR +  # Green color start
                        "Loading checkpoints for "
                        f"backtest range: {backtest_date_range}" +
                        COLOR_RESET
                    )

                backtest_results, missing = self.load_checkpoints(
                    active_algorithm_ids,
                    backtest_date_range,
                    backtest_storage_directory
                )
                strategies_to_run = [
                    strategy for strategy in active_strategies
                    if strategy.algorithm_id in missing
                ]

                if show_progress:
                    if len(strategies_to_run) == 0:
                        print(
                            GREEN_COLOR +
                            f"Found {len(backtest_results)} checkpoints. "
                            "No remaining strategies to run." +
                            COLOR_RESET
                        )
                    else:
                        print(
                            GREEN_COLOR +
                            f"Found {len(backtest_results)} checkpoints." +
                            COLOR_RESET
                        )

                if len(strategies_to_run) != 0:
                    # Run backtests for active strategies only
                    for strategy in tqdm(
                        strategies_to_run,
                        colour="green",
                        desc=f"{GREEN_COLOR}Running backtests "
                             f"for {start_date} "
                             f"to {end_date}{COLOR_RESET}"
                    ):
                        backtest_results.append(
                            self.run_vector_backtest(
                                backtest_date_range=backtest_date_range,
                                initial_amount=initial_amount,
                                strategy=strategy,
                                snapshot_interval=snapshot_interval,
                                risk_free_rate=risk_free_rate,
                                skip_data_sources_initialization=True,
                                market=market,
                                trading_symbol=trading_symbol,
                                backtest_storage_directory=(
                                    backtest_storage_directory
                                ),
                                show_progress=False
                            )
                        )

                # Apply filter function after each date range to determine
                # which strategies continue to the next period
                if window_filter_function is not None:
                    backtest_results = window_filter_function(
                        backtest_results, backtest_date_range
                    )
                    active_algorithm_ids = [
                        backtest.algorithm_id for backtest in backtest_results
                    ]
                    active_strategies = [
                        strategy for strategy in active_strategies
                        if strategy.algorithm_id in active_algorithm_ids
                    ]

                backtests_ordered_by_algorithm = {
                    **backtests_ordered_by_algorithm,
                    **{
                        backtest.algorithm_id:
                            backtests_ordered_by_algorithm.get(
                                backtest.algorithm_id, []
                            ) + [backtest]
                        for backtest in backtest_results
                    }
                }

                # Remove all algorithm_id entries that are no longer active
                backtests_ordered_by_algorithm = {
                    alg_id: backtests_ordered_by_algorithm[alg_id]
                    for alg_id in active_algorithm_ids
                }

                # Free up memory
                del backtest_results
                gc.collect()

            backtests = []

            for algorith_id in backtests_ordered_by_algorithm.keys():
                backtests.append(
                    combine_backtests(
                        backtests_ordered_by_algorithm[algorith_id]
                    )
                )

            # Apply final filter function if set
            if final_filter_function is not None:
                backtests = final_filter_function(backtests)

            if show_progress:
                print(GREEN_COLOR + "Saving all backtests ..." + COLOR_RESET)

            # Save final combined backtests to storage directory
            save_backtests_to_directory(
                backtests=backtests,
                directory_path=backtest_storage_directory,
            )

            if show_progress:
                print(GREEN_COLOR + "All backtests saved" + COLOR_RESET)

            # Free up memory
            del backtests_ordered_by_algorithm
            gc.collect()

        return backtests

    def run_vector_backtests(
        self,
        initial_amount,
        strategies: List,
        backtest_date_range: BacktestDateRange = None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        risk_free_rate: Optional[float] = None,
        skip_data_sources_initialization: bool = False,
        show_progress: bool = True,
        market: Optional[str] = None,
        trading_symbol: Optional[str] = None,
        continue_on_error: bool = False,
        window_filter_function: Optional[
            Callable[[List[Backtest], BacktestDateRange], List[Backtest]]
        ] = None,
        final_filter_function: Optional[
            Callable[[List[Backtest]], List[Backtest]]
        ] = None,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
    ):
        """
        Run vectorized backtests for multiple strategies with checkpointing.
        Args:
            strategies: List of strategies to backtest.
            backtest_storage_directory: Directory to store backtests.
            risk_free_rate: Risk-free rate for backtest metrics.
            backtest_date_range: Single backtest date range to use
                for all strategies.
            backtest_date_ranges (List[BacktestDateRange]): List of backtes
                date ranges to use for all strategies.
            skip_data_sources_initialization (bool): Whether to skip the
                initialization of data sources.
            show_progress (bool): Whether to show a progress bar and
                debug for the different processing steps.
            window_filter_function (
                Optional[Callable[[List[Backtest], BacktestDateRange],
                List[Backtest]]]
            ):
                A function that takes a list of Backtest objects and
                the current BacktestDateRange, and returns a filtered
                list of Backtest objects. This is applied after each
                backtest date range when backtest_date_ranges
                is provided. Only the strategies from the filtered
                backtests will continue to the next date range. This allows
                for progressive filtering
                of strategies based on their performance in previous periods.

                The function signature should be:
                    def filter_function(
                        backtests: List[Backtest],
                        backtest_date_range: BacktestDateRange
                    ) -> List[Backtest]
            final_filter_function (
                Optional[Callable[[List[Backtest]], List[Backtest]]]
            ):
                A function that takes a list of Backtest objects and
                returns a filtered list of Backtest objects. This is applied
                after all backtest date ranges have been processed when
                backtest_date_ranges is provided. Only the strategies from
                the filtered backtests will be returned as the final result.
                This allows for final filtering of strategies based on
                their overall performance across all periods. The function
                signature should be:
                    def filter_function(
                        backtests: List[Backtest]
                    ) -> List[Backtest]
        Returns:
            None
        """
        data_sources = []

        for strategy in strategies:
            data_sources.extend(strategy.data_sources)

        if risk_free_rate is None:

            if show_progress:
                print(
                    GREEN_COLOR +
                    "Retrieving risk free rate for metrics calculation ..." +
                    COLOR_RESET
                )
            risk_free_rate = get_risk_free_rate_us()

            if show_progress:
                print(
                    GREEN_COLOR,
                    f"Retrieving risk free rate of: {risk_free_rate}" +
                    COLOR_RESET
                )

        if backtest_date_range is None and backtest_date_ranges is None:
            raise OperationalException(
                "Either backtest_date_range or backtest_date_ranges must be "
                "provided"
            )

        # Run backtests for a single date range
        if backtest_date_range is not None:

            if not skip_data_sources_initialization:
                self.initialize_data_sources_backtest(
                    data_sources,
                    backtest_date_range,
                    show_progress=show_progress
                )

            backtests = []

            for strategy in tqdm(
                strategies,
                    colour="green",
                    desc=f"{GREEN_COLOR}Running backtests{COLOR_RESET}"
            ):
                backtests.append(
                    self.run_vector_backtest(
                        backtest_date_range=backtest_date_range,
                        initial_amount=initial_amount,
                        strategy=strategy,
                        snapshot_interval=snapshot_interval,
                        risk_free_rate=risk_free_rate,
                        skip_data_sources_initialization=True,
                        market=market,
                        trading_symbol=trading_symbol,
                        continue_on_error=continue_on_error,
                        backtest_storage_directory=backtest_storage_directory,
                        show_progress=False,
                    )
                )

            # Apply filter function if set
            if window_filter_function is not None:
                backtests = window_filter_function(
                    backtests, backtest_date_range
                )

            # Apply final filter function if set
            if final_filter_function is not None:
                backtests = final_filter_function(backtests)

            if show_progress:
                print(
                    GREEN_COLOR +
                    f"Saving {len(backtests)} backtests to storage ..." +
                    COLOR_RESET
                )

            if backtest_storage_directory is not None:
                save_backtests_to_directory(
                    backtests=backtests,
                    directory_path=backtest_storage_directory,
                )

            return backtests
        else:
            backtests_ordered_by_algorithm = {}
            active_strategies = strategies.copy()
            active_algorithm_ids = [
                strategy.algorithm_id for strategy in active_strategies
            ]

            # Make sure that the backtest date ranges are
            # sorted by start date and are unique
            unique_date_ranges = set(backtest_date_ranges)
            backtest_date_ranges = sorted(
                unique_date_ranges, key=lambda x: x.start_date
            )

            for backtest_date_range in tqdm(
                backtest_date_ranges,
                colour="green",
                desc=f"{GREEN_COLOR}Running backtests "
                     f"for all date ranges{COLOR_RESET}"
            ):

                if not skip_data_sources_initialization:
                    self.initialize_data_sources_backtest(
                        data_sources,
                        backtest_date_range,
                        show_progress=show_progress
                    )

                backtest_results = []
                start_date = backtest_date_range \
                    .start_date.strftime('%Y-%m-%d')
                end_date = backtest_date_range.end_date.strftime('%Y-%m-%d')

                # Run backtests for active strategies only
                for strategy in tqdm(
                    strategies,
                    colour="green",
                    desc=f"{GREEN_COLOR}Running backtests "
                         f"for {start_date} to {end_date}{COLOR_RESET}"
                ):
                    backtest_results.append(
                        self.run_vector_backtest(
                            backtest_date_range=backtest_date_range,
                            initial_amount=initial_amount,
                            strategy=strategy,
                            snapshot_interval=snapshot_interval,
                            risk_free_rate=risk_free_rate,
                            skip_data_sources_initialization=True,
                            market=market,
                            trading_symbol=trading_symbol,
                            show_progress=False
                        )
                    )

                # Apply filter function after each date range to determine
                # which strategies continue to the next period
                if window_filter_function is not None:
                    backtest_results = window_filter_function(
                        backtest_results, backtest_date_range
                    )
                    active_algorithm_ids = [
                        backtest.algorithm_id for backtest in backtest_results
                    ]
                    active_strategies = [
                        strategy for strategy in active_strategies
                        if strategy.algorithm_id in active_algorithm_ids
                    ]

                backtests_ordered_by_algorithm = {
                    **backtests_ordered_by_algorithm,
                    **{
                        backtest.algorithm_id:
                            backtests_ordered_by_algorithm.get(
                                backtest.algorithm_id, []
                            ) + [backtest]
                        for backtest in backtest_results
                    }
                }

                # Remove all algorithm_id entries that are no longer active
                backtests_ordered_by_algorithm = {
                    alg_id: backtests_ordered_by_algorithm[alg_id]
                    for alg_id in active_algorithm_ids
                }

                # Free up memory
                del backtest_results
                gc.collect()

            backtests = []

            for algorith_id in backtests_ordered_by_algorithm.keys():
                backtests.append(
                    combine_backtests(
                        backtests_ordered_by_algorithm[algorith_id]
                    )
                )

            # Apply final filter function if set
            if final_filter_function is not None:
                backtests = final_filter_function(backtests)

            if backtest_storage_directory is not None:
                if show_progress:
                    print(
                        GREEN_COLOR +
                        "Saving all backtests ..." +
                        COLOR_RESET
                    )

                # Save final combined backtests to storage directory
                save_backtests_to_directory(
                    backtests=backtests,
                    directory_path=backtest_storage_directory,
                )

                if show_progress:
                    print(
                        GREEN_COLOR +
                        "All backtests saved" +
                        COLOR_RESET
                    )

            # Free up memory
            del backtests_ordered_by_algorithm
            gc.collect()

        return backtests

    def run_vector_backtest(
        self,
        backtest_date_range: BacktestDateRange,
        strategy,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        metadata: Optional[Dict[str, str]] = None,
        risk_free_rate: Optional[float] = None,
        skip_data_sources_initialization: bool = False,
        initial_amount: float = None,
        market: str = None,
        trading_symbol: str = None,
        continue_on_error: bool = False,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
        show_progress=False,
    ) -> Backtest:
        """
        Run vectorized backtests for a strategy. The provided
        strategy needs to have its 'generate_buy_signals' and
        'generate_sell_signals' methods implemented to support vectorized
        backtesting.

        Args:
            backtest_date_range: The date range to run the backtest for
                (instance of BacktestDateRange)
            initial_amount: The initial amount to start the backtest with.
                This will be the amount of trading currency that the backtest
                portfolio will start with.
            strategy (TradingStrategy) (Optional): The strategy object
                that needs to be backtested.
            snapshot_interval (SnapshotInterval): The snapshot
                interval to use for the backtest. This is used to determine
                how often the portfolio snapshot should be taken during the
                backtest. The default is TRADE_CLOSE, which means that the
                portfolio snapshot will be taken at the end of each trade.
            risk_free_rate (Optional[float]): The risk-free rate to use for
                the backtest. This is used to calculate the Sharpe ratio
                and other performance metrics. If not provided, the default
                risk-free rate will be tried to be fetched from the
                US Treasury website.
            metadata (Optional[Dict[str, str]]): Metadata to attach to the
                backtest report. This can be used to store additional
                information about the backtest, such as the author, version,
                parameters or any other relevant information.
            skip_data_sources_initialization (bool): Whether to skip the
                initialization of data sources. This is useful when the data
                sources are already initialized, and you want to skip the
                initialization step. This will speed up the backtesting
                process, but make sure that the data sources are already
                initialized before calling this method.
            market (str): The market to use for the backtest. This is used
                to create a portfolio configuration if no portfolio
                configuration is provided in the strategy.
            trading_symbol (str): The trading symbol to use for the backtest.
                This is used to create a portfolio configuration if no
                portfolio configuration is provided in the strategy.
            initial_amount (float): The initial amount to start the
                backtest with. This will be the amount of trading currency
                that the portfolio will start with. If not provided,
                the initial amount from the portfolio configuration will
                be used.
            continue_on_error (bool): Whether to continue running other
                backtests if an error occurs in one of the backtests. If set
                to True, the backtest will return an empty Backtest instance
                in case of an error. If set to False, the error will be raised.
            backtest_storage_directory (Union[str, Path]): The directory
                to save the backtest to after it is completed. This is
                useful for long-running backtests that might take a
                while to complete.
            show_progress (bool): Whether to show progress bars during
                data source initialization. This is useful for long-running
                initialization processes.

        Returns:
            Backtest: Instance of Backtest
        """

        if not skip_data_sources_initialization:
            self.initialize_data_sources_backtest(
                strategy.data_sources,
                backtest_date_range,
                show_progress=show_progress
            )

        if risk_free_rate is None:
            logger.info("No risk free rate provided, retrieving it...")
            risk_free_rate = get_risk_free_rate_us()

            if risk_free_rate is None:
                raise OperationalException(
                    "Could not retrieve risk free rate for backtest metrics."
                    "Please provide a risk free rate as an argument "
                    "when running your backtest or make sure "
                    "you have an internet connection"
                )

        self.validate_strategy_for_vector_backtest(strategy)

        try:

            if show_progress:
                start_date = backtest_date_range \
                    .start_date.strftime('%Y-%m-%d')
                end_date = backtest_date_range.end_date.strftime(
                    '%Y-%m-%d')
                print(
                    GREEN_COLOR +
                    f"Running backtest for {start_date} to {end_date}..." +
                    COLOR_RESET
                )

            run = self.create_vector_backtest(
                strategy=strategy,
                backtest_date_range=backtest_date_range,
                risk_free_rate=risk_free_rate,
                market=market,
                trading_symbol=trading_symbol,
                initial_amount=initial_amount
            )
            backtest = Backtest(
                algorithm_id=strategy.algorithm_id,
                backtest_runs=[run],
                risk_free_rate=risk_free_rate,
                backtest_summary=generate_backtest_summary_metrics(
                    [run.backtest_metrics]
                )
            )
        except Exception as e:
            logger.error(
                f"Error occurred during vector backtest for strategy "
                f"{strategy.strategy_id}: {str(e)}"
            )

            if continue_on_error:
                backtest = Backtest(
                    algorithm_id=strategy.algorithm_id,
                    backtest_runs=[],
                    risk_free_rate=risk_free_rate,
                )
            else:
                raise e

        # Add the metadata to the backtest
        if metadata is None:

            if strategy.metadata is None:
                backtest.metadata = {}
            else:
                backtest.metadata = strategy.metadata
        else:
            backtest.metadata = metadata

        return backtest

    def _get_risk_free_rate(self) -> float:
        """
        Get the risk-free rate from the configuration service.

        Returns:
            float: The risk-free rate.
        """
        risk_free_rate = get_risk_free_rate_us()

        if risk_free_rate is None:
            raise OperationalException(
                "Could not retrieve risk free rate."
                "Please provide a risk free as an argument when running "
                "your backtest or make sure you have an internet "
                "connection"
            )

        return risk_free_rate
