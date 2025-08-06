import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import BacktestResult, \
    TimeUnit, Trade, OperationalException, Observable, BacktestDateRange, \
    DATETIME_FORMAT_BACKTESTING, Backtest, TradeStatus, PortfolioSnapshot, \
    DataType
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics

logger = logging.getLogger(__name__)
BACKTEST_REPORT_FILE_NAME_PATTERN = (
    r"^report_\w+_backtest-start-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"backtest-end-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"created-at_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}\.json$"
)
BACKTEST_REPORT_DIRECTORY_PATTERN = (
    r"^report_\w+_backtest-start-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"backtest-end-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"created-at_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}$"
)


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

    def create_vector_backtest(
        self,
        strategy,
        backtest_date_range: BacktestDateRange,
        initial_amount,
        position_size: float = 1.0,
        risk_free_rate: float = 0.027
    ):
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
        index = main_df.index

        # === Signal computation ===
        buy_signal = buy_fn(data)
        sell_signal = sell_fn(data)

        # Reindex to match main_df (avoid alignment issues)
        buy_signal = buy_signal.reindex(index, fill_value=False)
        sell_signal = sell_signal.reindex(index, fill_value=False)

        signal = pd.Series(0, index=index)
        signal[buy_signal] = 1
        signal[sell_signal] = -1
        signal = signal.replace(0, np.nan).ffill().shift(1).fillna(0)

        # === Portfolio computation ===
        returns = close.pct_change().fillna(0)
        position = signal
        strategy_returns = position * returns

        holdings = (strategy_returns + 1).cumprod() * initial_amount
        total_value = holdings
        net_gain = total_value - initial_amount

        # === Trade generation (semi-vectorized) ===
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

        # === Snapshots ===
        snapshots = [
            PortfolioSnapshot(
                created_at=pd.Timestamp(ts),
                unallocated=0.0,
                total_value=total_value.loc[ts],
                total_net_gain=net_gain.loc[ts]
            )
            for ts in index
        ]

        backtest_start = pd.Timestamp(index[0]).to_pydatetime() if len(
            index) > 0 else None
        backtest_end = pd.Timestamp(index[-1]).to_pydatetime() if len(
            index) > 0 else None

        backtest_result = BacktestResult(
            trading_symbol="EUR",
            name="vector_backtest",
            initial_unallocated=initial_amount,
            number_of_runs=1,
            portfolio_snapshots=snapshots,
            trades=trades,
            orders=[],
            positions=[],
            created_at=datetime.now(timezone.utc),
            backtest_date_range=backtest_date_range,
            backtest_start_date=backtest_start,
            backtest_end_date=backtest_end,
            symbols=[]
        )

        backtest_metrics = create_backtest_metrics(
            backtest_result, risk_free_rate=risk_free_rate
        )

        return Backtest(
            backtest_metrics=backtest_metrics,
            backtest_results=backtest_result
        )

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
            risk_free_rate: The risk-free rate to use in the calculations
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

        backtest_result = BacktestResult(
            name=algorithm.name,
            backtest_date_range=backtest_date_range,
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
            backtest_result, risk_free_rate=risk_free_rate
        )
        return Backtest(
            backtest_results=backtest_result,
            backtest_metrics=backtest_metrics,
            strategy_related_paths=strategy_related_paths,
            data_file_paths=self._data_provider_service.get_data_files(),
        )

    def get_backtest(
        self,
        algorithm,
        backtest_date_range: BacktestDateRange,
        directory
    ) -> Optional[Backtest]:
        """
        Get a backtest for the given algorithm and date range.

        Args:
            algorithm: The algorithm to get the backtest for
            backtest_date_range: The date range of the backtest
            directory: The directory where the backtest report will be saved

        Returns:
            Optional[Backtest]: The backtest containing the
                results and metrics.
        """

        if not os.path.exists(directory):
            return None

        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)

            if not os.path.isdir(path):
                continue

            try:
                # Load the backtest report
                backtest = Backtest.open(path)

                # Check if the algorithm name and date range match
                if backtest.backtest_results.name == algorithm.name \
                    and backtest.backtest_results.backtest_date_range \
                        == backtest_date_range:
                    return backtest
            except Exception:
                continue

        return None

    @staticmethod
    def create_report_directory_name(backtest: Backtest) -> str:
        """
        Function to create a directory name for a backtest report.
        The directory name will be automatically generated based on the
        algorithm name and creation date.

        Args:
            backtest (Backtest): The backtest object containing the results
                and metrics.

        Returns:
            directory_name: str The directory name for the
                backtest report file.
        """
        created_at = backtest.backtest_results\
            .created_at.strftime(DATETIME_FORMAT_BACKTESTING)
        date_range = backtest.backtest_results.backtest_date_range
        backtest_start_date = date_range.start_date
        backtest_end_date = date_range.end_date
        name = backtest.backtest_results.name
        start_date = backtest_start_date.strftime(DATETIME_FORMAT_BACKTESTING)
        end_date = backtest_end_date.strftime(DATETIME_FORMAT_BACKTESTING)
        directory_name = f"report_{name}_backtest-start-date_" \
            f"{start_date}_backtest-end-date_{end_date}_{created_at}"
        return directory_name
