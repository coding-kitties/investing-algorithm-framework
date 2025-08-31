import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Union

import numpy as np
import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import BacktestRun, \
    TimeUnit, Trade, OperationalException, Observable, BacktestDateRange, \
    Backtest, TradeStatus, PortfolioSnapshot, \
    DataType
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics

logger = logging.getLogger(__name__)


class BacktestService(Observable):
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
        performance_service,
        configuration_service,
        portfolio_configuration_service,
    ):
        super().__init__()
        self._order_service = order_service
        self._trade_service = trade_service
        self._portfolio_service = portfolio_service
        self._performance_service = performance_service
        self._portfolio_snapshot_service = portfolio_snapshot_service
        self._position_repository = position_repository
        self._configuration_service = configuration_service
        self._portfolio_configuration_service = portfolio_configuration_service
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
        if not hasattr(strategy, 'buy_signal_vectorized'):
            raise OperationalException(
                "Strategy must define a vectorized buy signal function "
                "(buy_signal_vectorized)."
            )
        if not hasattr(strategy, 'sell_signal_vectorized'):
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
        initial_amount,
        position_size: float = 1.0,
        risk_free_rate: float = 0.027
    ) -> BacktestRun:
        """
        Vectorized backtest using a strategy's buy/sell signals.

        Args:
            strategy: The strategy to use for the backtest.
            backtest_date_range: The date range for the backtest.
            initial_amount: The initial capital.
            position_size: Amount per trade.
            risk_free_rate: Annualized risk-free rate.

        Returns:
            Backtest: backtest result with trades and performance.
        """
        # Load all data sources
        data_sources = strategy.data_sources
        data = self._data_provider_service.get_vectorized_backtest_data(
            data_sources=data_sources,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date
        )

        # Verify signal functions
        buy_fn = getattr(strategy, 'buy_signal_vectorized', None)
        sell_fn = getattr(strategy, 'sell_signal_vectorized', None)

        if not buy_fn or not sell_fn:
            raise OperationalException(
                "Strategy must define vectorized buy/sell signal functions."
            )

        # Select main OHLCV source (most granular)
        ohlcv_sources = [ds for ds in data_sources if
                         DataType.OHLCV.equals(ds.data_type)]

        if not ohlcv_sources:
            raise OperationalException("No OHLCV data sources found.")

        most_granular_ds = min(ohlcv_sources, key=lambda ds: ds.time_frame)
        main_df = data[most_granular_ds.get_identifier()]
        close = main_df['Close']

        index = self._get_data_frame_index(main_df)
        # index = main_df.index

        # Signal computation
        buy_signal = buy_fn(data)
        sell_signal = sell_fn(data)

        # Reindex to match main_df (avoid alignment issues)
        buy_signal = buy_signal.reindex(index, fill_value=False)
        sell_signal = sell_signal.reindex(index, fill_value=False)

        signal = pd.Series(0, index=index)
        signal[buy_signal] = 1
        signal[sell_signal] = -1
        signal = signal.replace(0, np.nan).ffill().shift(1).fillna(0)

        # Portfolio computation
        returns = close.pct_change().fillna(0)
        position = signal
        strategy_returns = position * returns

        holdings = (strategy_returns + 1).cumprod() * initial_amount
        total_value = holdings
        net_gain = total_value - initial_amount

        # Trade generation (semi-vectorized)
        trades = []
        position_state = 0
        trade_open_price = None
        trade_open_date = None

        for i in range(len(index)):
            current_signal = signal.iloc[i]
            current_price = close.iloc[i]
            current_date = index[i]

            if position_state == 0 and current_signal != 0:
                position_state = current_signal
                trade_open_price = current_price
                trade_open_date = current_date
            elif position_state != 0 and current_signal == -position_state:
                net_gain_val = (current_price - trade_open_price) \
                    * position_state * position_size
                trades.append(Trade(
                    id=len(trades) + 1,
                    orders=[],
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    available_amount=0,
                    remaining=0,
                    filled_amount=position_size,
                    opened_at=trade_open_date,
                    closed_at=current_date,
                    open_price=trade_open_price,
                    amount=position_size,
                    net_gain=net_gain_val,
                    status=TradeStatus.CLOSED,
                    cost=position_size * trade_open_price
                ))
                trade_open_price = None
                trade_open_date = None
                position_state = 0

        # Snapshots
        snapshots = [
            PortfolioSnapshot(
                created_at=pd.Timestamp(ts),
                unallocated=0.0,
                total_value=total_value.loc[ts],
                total_net_gain=net_gain.loc[ts]
            )
            for ts in index
        ]

        run = BacktestRun(
            trading_symbol="EUR",
            initial_unallocated=initial_amount,
            number_of_runs=1,
            portfolio_snapshots=snapshots,
            trades=trades,
            orders=[],
            positions=[],
            created_at=datetime.now(timezone.utc),
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            symbols=[]
        )
        backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        run.backtest_metrics = backtest_metrics
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

    def _get_initial_unallocated(
        self
    ) -> float:
        """
        Get the initial unallocated amount for the backtest.

        Args:
            algorithm: The algorithm to create the backtest report for
            backtest_date_range: The backtest date range of the backtest

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
        )
