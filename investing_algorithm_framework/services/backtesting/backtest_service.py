import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from investing_algorithm_framework.domain import BacktestResult, \
    TimeUnit, TradingDataType, \
    OperationalException, Observable, BacktestDateRange, \
    DATETIME_FORMAT_BACKTESTING, Backtest
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
        self._data_index = {
            TradingDataType.OHLCV: {},
            TradingDataType.TICKER: {}
        }
        self._performance_service = performance_service
        self._portfolio_snapshot_service = portfolio_snapshot_service
        self._position_repository = position_repository
        self._configuration_service = configuration_service
        self._portfolio_configuration_service = portfolio_configuration_service
        self._data_provider_service = data_provider_service

    def generate_schedule(
        self,
        strategies,
        tasks,
        start_date,
        end_date
    ) -> Dict[datetime, Dict[str, List[str]]]:
        """
        Generates a dict-based schedule: datetime => {strategy_ids, task_ids}

        Args:
            strategies (list): Strategies with intervals and time units.
            tasks (list): List of task IDs (run for every timestamp).
            start_date (datetime): Start of the simulation.
            end_date (datetime): End of the simulation.

        Returns:
            dict: schedule[datetime] =
                {"strategy_ids": [...], "task_ids": [...]}
        """
        schedule = defaultdict(
            lambda: {"strategy_ids": set(), "task_ids": set(tasks)}
        )

        for strategy in strategies:
            strategy_id = strategy.strategy_profile.strategy_id
            interval = strategy.strategy_profile.interval
            time_unit = strategy.strategy_profile.time_unit

            # Convert interval to seconds
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

            # Convert sets to sorted lists (optional, for deterministic iteration)
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
