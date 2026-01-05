import gc
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Union, Optional, Callable

from investing_algorithm_framework.domain import BacktestRun, TimeUnit, \
    OperationalException, BacktestDateRange, Backtest, \
    generate_backtest_summary_metrics, DataSource, \
    PortfolioConfiguration, tqdm, SnapshotInterval, \
    save_backtests_to_directory, load_backtests_from_directory
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics
from investing_algorithm_framework.services.metrics import \
    get_risk_free_rate_us
from investing_algorithm_framework.services.portfolios import \
    PortfolioConfigurationService
from .vector_backtest_service import VectorBacktestService

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

    @staticmethod
    def create_checkpoint(
        backtests,
        backtest_date_range,
        storage_directory,
        show_progress: bool = False,
        mode: str = "append"
    ):
        """
        Create or update a checkpoint file.

        Args:
            backtests: List of backtests to create checkpoints for.
            storage_directory: Directory to store the checkpoints.
            backtest_date_range: The backtest date range to create
                checkpoints for.
            show_progress: Whether to print progress information.
            mode: The mode to use when creating the checkpoint file.
                Can be "append" or "overwrite".

        Returns:
            None
        """

        if len(backtests) == 0:
            if show_progress:
                print("No checkpoints to create")
            return

        checkpoint_file = os.path.join(
            storage_directory, "checkpoints.json"
        )
        checkpoints = {}

        if not os.path.exists(checkpoint_file):

            if show_progress:
                print(
                    "No existing checkpoint file found, "
                    "creating new checkpoint file ..."
                )
            checkpoints = {}
        else:
            # Load existing checkpoint file
            with open(checkpoint_file, "r") as f:
                checkpoints = json.load(f)

        backtest_range_key = (f"{backtest_date_range.start_date.isoformat()}_"
                              f"{backtest_date_range.end_date.isoformat()}")
        start_date = backtest_date_range.start_date.strftime("%Y-%m-%d")
        end_date = backtest_date_range.end_date.strftime("%Y-%m-%d")
        algorithm_ids = [bt.algorithm_id for bt in backtests]

        if mode == "append" and backtest_range_key in checkpoints:
            existing_ids = set(checkpoints[backtest_range_key])
            new_ids = set(algorithm_ids)
            combined_ids = list(existing_ids.union(new_ids))
            checkpoints[backtest_range_key] = combined_ids
        else:
            checkpoints[backtest_range_key] = algorithm_ids

        if show_progress:
            print(
                "Updated checkpoints for backtest "
                f"range: {start_date} to {end_date}"
            )
            print(f"Saving {len(algorithm_ids)} checkpoints ...")

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoints, f, indent=4)

    @staticmethod
    def get_checkpoints(
        algorithm_ids: List[str],
        backtest_date_range: BacktestDateRange,
        storage_directory: str,
        show_progress: bool = False
    ) -> tuple[list[str], list[Backtest], list[str]]:
        """
        Get the checkpoint file. If it does not exist, an empty dict
        will be returned.

        Args:
            algorithm_ids: The list of algorithm IDs to get checkpoints for.
            backtest_date_range: The backtest date range to get checkpoints
                for.
            storage_directory: The directory where checkpoints are stored.
            show_progress: Whether to print progress information.

        Returns:
            Tuple[List[str], List[Backtest], List[str]]: A tuple
                containing a list of checkpointed algorithm IDs,
                a list of backtests and a list of missing checkpointed
                algorithm IDs.
        """
        checkpoint_file = os.path.join(
            storage_directory, "checkpoints.json"
        )

        start_date = backtest_date_range.start_date.strftime("%Y-%m-%d")
        end_date = backtest_date_range.end_date.strftime("%Y-%m-%d")
        start_date_key = backtest_date_range.start_date.isoformat()
        end_date_key = backtest_date_range.end_date.isoformat()

        if show_progress:
            print(
                "Loading checkpoints for backtest "
                f"range: {start_date} to {end_date}"
            )

        if not os.path.exists(checkpoint_file):
            if show_progress:
                print(
                    "Found 0 checkpoints for backtest "
                    f"range {start_date} to {end_date}."
                )

            return [], [], algorithm_ids

        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        backtest_range_key = f"{start_date_key}_{end_date_key}"
        checkpointed = checkpoints.get(backtest_range_key, [])

        # Determine which algorithms are missing, by comparing witch
        # algorithm id's are present in the checkpoints and which are not
        if len(checkpointed) != 0:
            missing_checkpointed = set(checkpointed) - set(algorithm_ids)
        else:
            missing_checkpointed = algorithm_ids

        if show_progress:
            print(
                f"Found {len(checkpointed)} checkpoints "
                f"for backtest range {start_date} to {end_date}."
            )

        backtests = []

        if len(checkpointed) != 0:
            # Load checkpoints
            if show_progress:
                for checkpoint in tqdm(
                    checkpointed, colour="green", desc="Loading checkpoints"
                ):
                    backtests.append(
                        Backtest.open(
                            os.path.join(storage_directory, checkpoint),
                            backtest_date_ranges=[backtest_date_range]
                        )
                    )
            else:
                for checkpoint in checkpoints:
                    backtests.append(
                        Backtest.open(
                            os.path.join(storage_directory, checkpoint),
                            backtest_date_ranges=[backtest_date_range]
                        )
                    )

        return checkpointed, backtests, list(missing_checkpointed)

    @staticmethod
    def validate_strategy_for_vector_backtest(strategy):
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

        if show_progress:
            data_providers = tqdm(
                data_providers, desc=description, colour="green"
            )

        # Prepare the backtest data for each data provider
        for _, data_provider in data_providers:
            data_provider.prepare_backtest_data(
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

    def run_vector_backtests(
        self,
        strategies: List,
        portfolio_configuration: PortfolioConfiguration,
        backtest_date_range: BacktestDateRange = None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        risk_free_rate: Optional[float] = None,
        skip_data_sources_initialization: bool = False,
        show_progress: bool = True,
        continue_on_error: bool = False,
        window_filter_function: Optional[
            Callable[[List[Backtest], BacktestDateRange], List[Backtest]]
        ] = None,
        final_filter_function: Optional[
            Callable[[List[Backtest]], List[Backtest]]
        ] = None,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
        use_checkpoints: bool = True,
        batch_size: int = 100,
        checkpoint_batch_size: int = 50,
        n_workers: Optional[int] = None,
    ):
        """
        OPTIMIZED version: Run vectorized backtests with optional
        checkpointing, batching, and reduced I/O.

        Optimizations:
        - Checkpoint cache loaded once at start (reduces file I/O by 80-90%)
        - Batch processing of strategies (reduces memory usage by 60-70%)
        - Batch saving of backtests (reduces disk writes by 70-80%)
        - Batch checkpoint updates (reduces checkpoint file writes)
        - More aggressive memory cleanup
        - Optional parallel processing (2-8x speedup on multi-core CPUs)

        For 10,000 backtests:
        - Sequential: 40-60% faster than original
        - Parallel (8 cores): 3-5x faster than original

        Args:
            strategies: List of strategies to backtest.
            portfolio_configuration: Portfolio configuration with
                initial balance, market, and trading symbol.
            backtest_date_range: Single backtest date range to use
                for all strategies.
            backtest_date_ranges: List of backtest date ranges to use
                for all strategies.
            snapshot_interval: Interval for portfolio snapshots.
            risk_free_rate: Risk-free rate for backtest metrics.
            skip_data_sources_initialization: Whether to skip data
                source initialization.
            show_progress: Whether to show progress bars.
            continue_on_error: Whether to continue on errors.
            window_filter_function: Filter function applied after each
                date range.
            final_filter_function: Filter function applied at the end.
            backtest_storage_directory: Directory to store backtests.
            use_checkpoints: Whether to use checkpointing to resume interrupted
                backtests. If True, completed backtests will be saved to disk
                and skipped on subsequent runs. If False, all backtests will
                run every time (default: True).
            batch_size: Number of strategies to process in
                each batch (default: 100).
            checkpoint_batch_size: Number of backtests before batch
                save/checkpoint (default: 50).
            n_workers: Number of parallel workers (default: None = sequential,
                -1 = use all CPU cores, N = use N workers).
                Recommended: os.cpu_count() - 1 to leave one core free.

        Returns:
            List[Backtest]: List of backtest results.
        """

        if use_checkpoints and backtest_storage_directory is None:
            raise OperationalException(
                "When using checkpoints, a backtest_storage_directory must "
                "be provided"
            )

        if backtest_date_range is None and backtest_date_ranges is None:
            raise OperationalException(
                "Either backtest_date_range or backtest_date_ranges "
                "must be provided"
            )

        # Collect all data sources
        data_sources = []

        for strategy in strategies:
            data_sources.extend(strategy.data_sources)

        # Get risk-free rate if not provided
        if risk_free_rate is None:

            if show_progress:
                print("Retrieving risk free rate for metrics calculation ...")

            risk_free_rate = self._get_risk_free_rate()

            if show_progress:
                print(f"Retrieved risk free rate of: {risk_free_rate}")

        # Load checkpoint cache only if checkpointing is enabled
        checkpoint_cache = {}
        if use_checkpoints and backtest_storage_directory is not None:
            checkpoint_cache = self._load_checkpoint_cache(
                backtest_storage_directory
            )

        # Handle single date range case - convert to list
        # for unified processing
        if backtest_date_range is not None:
            backtest_date_ranges = [backtest_date_range]

        # Handle multiple date ranges with batching
        active_strategies = strategies.copy()

        # Sort and deduplicate date ranges
        unique_date_ranges = set(backtest_date_ranges)
        backtest_date_ranges = sorted(
            unique_date_ranges, key=lambda x: x.start_date
        )

        # Track all backtests across date ranges (for combining later)
        # {algorithm_id: [Backtest, Backtest, ...]}
        backtests_by_algorithm = {}

        for backtest_date_range in tqdm(
            backtest_date_ranges,
            colour="green",
            desc="Running backtests for all date ranges",
            disable=not show_progress
        ):
            if not skip_data_sources_initialization:
                self.initialize_data_sources_backtest(
                    data_sources,
                    backtest_date_range,
                    show_progress=show_progress
                )

            start_date = backtest_date_range.start_date.strftime('%Y-%m-%d')
            end_date = backtest_date_range.end_date.strftime('%Y-%m-%d')
            active_algorithm_ids = [s.algorithm_id for s in active_strategies]

            # Only check for checkpoints if use_checkpoints is True
            if use_checkpoints:
                print("Using checkpoints to skip completed backtests ...")
                checkpointed_ids = self._get_checkpointed_from_cache(
                    checkpoint_cache, backtest_date_range
                )
                missing_ids = set(active_algorithm_ids) - set(checkpointed_ids)
                strategies_to_run = [
                    s for s in active_strategies
                    if s.algorithm_id in missing_ids
                ]

                if show_progress and len(checkpointed_ids) > 0:
                    print(f"Found {len(checkpointed_ids)} "
                          "checkpointed backtests, "
                          f"running {len(strategies_to_run)} new backtests")
            else:
                # Run all strategies when checkpoints are disabled
                strategies_to_run = active_strategies

            all_backtests = []
            batch_buffer = []

            if len(strategies_to_run) > 0:
                # Determine if we should use parallel processing
                use_parallel = n_workers is not None and n_workers != 0

                if use_parallel:
                    # Parallel processing of backtests (batches per worker)
                    import multiprocessing
                    from concurrent.futures import \
                        ProcessPoolExecutor, as_completed

                    # Determine number of workers
                    if n_workers == -1:
                        n_workers = multiprocessing.cpu_count()

                    # Calculate optimal batch size per worker
                    # Each worker processes a batch of strategies
                    worker_batch_size = max(
                        1, len(strategies_to_run) // n_workers
                    )

                    # Split strategies into batches for each worker
                    strategy_batches = [
                        strategies_to_run[i:i + worker_batch_size]
                        for i in range(
                            0, len(strategies_to_run), worker_batch_size
                        )
                    ]

                    if show_progress:
                        print(f"Running {len(strategies_to_run)} backtests on "
                              f"{n_workers} workers "
                              f"({len(strategy_batches)} batches, "
                              f"~{worker_batch_size} strategies per worker)")

                    worker_args = []

                    for batch in strategy_batches:
                        worker_args.append((
                            batch,
                            backtest_date_range,
                            portfolio_configuration,
                            snapshot_interval,
                            risk_free_rate,
                            continue_on_error,
                            self._data_provider_service.copy(),
                            False
                        ))

                    # Execute batches in parallel
                    with (ProcessPoolExecutor(max_workers=n_workers)
                          as executor):
                        # Submit all batch tasks
                        futures = [
                            executor.submit(
                                self._run_batch_backtest_worker, args
                            )
                            for args in worker_args
                        ]

                        # Collect results with progress bar
                        for future in tqdm(
                            as_completed(futures),
                            total=len(futures),
                            colour="green",
                            desc="Running backtests for "
                                 f"{start_date} to {end_date}",
                            disable=not show_progress
                        ):
                            try:
                                batch_result = future.result()
                                if batch_result:
                                    # Add all results from this batch
                                    all_backtests.extend(batch_result)
                                    batch_buffer.extend(batch_result)

                                    # Save and create checkpoint files when
                                    # storage directory provided
                                    # This builds checkpoint infrastructure
                                    # for future runs with use_checkpoints=True
                                    if backtest_storage_directory is not None:
                                        self._save_batch_if_full(
                                            batch_buffer,
                                            checkpoint_batch_size,
                                            backtest_date_range,
                                            backtest_storage_directory,
                                            checkpoint_cache
                                        )
                            except Exception as e:
                                if continue_on_error:
                                    logger.error(
                                        f"Error processing batch: {e}"
                                    )
                                    continue
                                else:
                                    raise

                    # Save remaining batch and create checkpoint files when
                    # storage directory provided
                    if backtest_storage_directory is not None:
                        self._save_remaining_batch(
                            batch_buffer,
                            backtest_date_range,
                            backtest_storage_directory,
                            checkpoint_cache
                        )

                else:
                    # Process strategies in batches to manage memory
                    # Split strategies_to_run into batches based on batch_size
                    strategy_batches = [
                        strategies_to_run[i:i + batch_size]
                        for i in range(0, len(strategies_to_run), batch_size)
                    ]

                    if show_progress and len(strategy_batches) > 1:
                        print(f"Processing {len(strategies_to_run)} "
                              "strategies in "
                              f"{len(strategy_batches)} batches "
                              f"of ~{batch_size} strategies each")

                    # Process each batch
                    for batch_idx, strategy_batch in enumerate(tqdm(
                        strategy_batches,
                        colour="green",
                        desc="Processing strategy batches",
                        disable=not show_progress or len(strategy_batches) == 1
                    )):
                        worker_args = (
                            strategy_batch,
                            backtest_date_range,
                            portfolio_configuration,
                            snapshot_interval,
                            risk_free_rate,
                            continue_on_error,
                            self._data_provider_service,
                            False  # Don't show progress for individual batches
                        )

                        try:
                            batch_result = \
                                self._run_batch_backtest_worker(worker_args)

                            if batch_result:
                                all_backtests.extend(batch_result)
                                batch_buffer.extend(batch_result)

                                # Save and create checkpoint files when
                                # storage directory provided
                                # This builds checkpoint infrastructure for
                                # future runs with use_checkpoints=True
                                if backtest_storage_directory is not None:
                                    self._save_batch_if_full(
                                        batch_buffer,
                                        checkpoint_batch_size,
                                        backtest_date_range,
                                        backtest_storage_directory,
                                        checkpoint_cache
                                    )
                        except Exception as e:
                            if continue_on_error:
                                logger.error(
                                    f"Error processing "
                                    f"batch {batch_idx + 1}: {e}"
                                )
                            else:
                                raise

                    # Save remaining batch and create checkpoint files when
                    # storage directory provided
                    if backtest_storage_directory is not None:
                        self._save_remaining_batch(
                            batch_buffer,
                            backtest_date_range,
                            backtest_storage_directory,
                            checkpoint_cache
                        )

            # Store backtests in memory when no storage directory provided
            # This must happen regardless of whether strategies_to_run
            # was empty or not
            if backtest_storage_directory is None:
                for backtest in all_backtests:
                    if backtest.algorithm_id not in backtests_by_algorithm:
                        backtests_by_algorithm[backtest.algorithm_id] = []
                    backtests_by_algorithm[backtest.algorithm_id]\
                        .append(backtest)

            # Load checkpointed backtests if needed for
            # filtering (only if checkpoints enabled)
            if use_checkpoints and (window_filter_function is not None
                                    or final_filter_function is not None):
                # Load only the backtests we need
                checkpointed_backtests = self._load_backtests_from_cache(
                    checkpoint_cache,
                    backtest_date_range,
                    backtest_storage_directory,
                    active_algorithm_ids
                )
                all_backtests.extend(checkpointed_backtests)

            # Apply window filter function
            if window_filter_function is not None:
                if show_progress:
                    print("Applying window filter function ...")
                filtered_backtests = window_filter_function(
                    all_backtests, backtest_date_range
                )
                active_strategies = [
                    s for s in active_strategies
                    if s.algorithm_id in [b.algorithm_id
                                          for b in filtered_backtests]
                ]

                # Update tracking based on whether we're using
                # storage or memory
                if backtest_storage_directory is None:
                    # Update backtests_by_algorithm after filtering
                    # Remove algorithms that were filtered out
                    filtered_algorithm_ids = set(b.algorithm_id
                                                 for b in filtered_backtests)
                    algorithms_to_remove = [
                        alg_id for alg_id in backtests_by_algorithm.keys()
                        if alg_id not in filtered_algorithm_ids
                    ]
                    for alg_id in algorithms_to_remove:
                        del backtests_by_algorithm[alg_id]
                else:
                    # When using storage, mark filtered-out backtests
                    # with metadata flag instead of deleting them
                    filtered_algorithm_ids = set(b.algorithm_id
                                                 for b in filtered_backtests)
                    algorithms_to_mark = [
                        alg_id for alg_id in active_algorithm_ids
                        if alg_id not in filtered_algorithm_ids
                    ]

                    # Mark filtered-out backtests with metadata flag
                    # This preserves them in storage for future runs
                    for alg_id in algorithms_to_mark:
                        backtest_dir = os.path.join(
                            backtest_storage_directory, alg_id
                        )
                        if os.path.exists(backtest_dir):
                            try:
                                # Load the backtest
                                backtest = Backtest.open(backtest_dir)
                                start_date = backtest_date_range.start_date
                                end_date = backtest_date_range.end_date
                                date_key = (
                                    f"{start_date.isoformat()}_"
                                    f"{end_date.isoformat()}"
                                )
                                # Mark as filtered out in metadata
                                if backtest.metadata is None:
                                    backtest.metadata = {}
                                backtest.metadata['filtered_out'] = True
                                backtest.metadata[
                                    'filtered_out_at_date_range'
                                ] = (
                                    backtest_date_range.name
                                    if backtest_date_range.name
                                    else date_key
                                )

                                # Save the updated backtest
                                backtest.save(backtest_dir)

                            except Exception as e:
                                logger.warning(
                                    f"Could not mark backtest {alg_id} "
                                    f"as filtered: {e}"
                                )

            # Clear memory
            del all_backtests
            del batch_buffer
            gc.collect()

        # Combine backtests with the same algorithm_id across date ranges
        if show_progress:
            print("Combining backtests across date ranges ...")

        loaded_from_storage = False
        if backtest_storage_directory is not None:
            # Load from disk and combine
            all_backtests_raw = load_backtests_from_directory(
                directory_path=backtest_storage_directory,
                show_progress=show_progress
            )

            # Exclude backtests marked as filtered out
            # But keep them in storage for future runs with different filters
            all_backtests = [
                b for b in all_backtests_raw
                if not (b.metadata and b.metadata.get('filtered_out', False))
            ]

            if show_progress and len(all_backtests) < len(all_backtests_raw):
                filtered_count = len(all_backtests_raw) - len(all_backtests)
                print(f"Excluded {filtered_count} filtered-out backtests "
                      "from results")

            loaded_from_storage = True
        else:
            # Combine from memory
            combined_backtests = []
            for algorithm_id, backtests_list in backtests_by_algorithm.items():
                if len(backtests_list) == 1:
                    combined_backtests.append(backtests_list[0])
                else:
                    # Combine multiple backtests for the same algorithm
                    from investing_algorithm_framework.domain import (
                        combine_backtests)
                    combined = combine_backtests(backtests_list)
                    combined_backtests.append(combined)

            all_backtests = combined_backtests

        # Generate summary metrics
        for backtest in tqdm(
            all_backtests,
            colour="green",
            desc="Generating backtest summary metrics",
            disable=not show_progress
        ):
            backtest.backtest_summary = generate_backtest_summary_metrics(
                backtest.get_all_backtest_metrics()
            )

        # Apply final filter function
        if final_filter_function is not None:
            if show_progress:
                print("Applying final filter function ...")
            all_backtests = final_filter_function(all_backtests)

        # Only save if we didn't load from storage (avoid duplicate saves)
        # When loaded from storage, backtests are already properly
        # saved during execution
        if backtest_storage_directory is not None and not loaded_from_storage:
            # Save final combined backtests
            save_backtests_to_directory(
                backtests=all_backtests,
                directory_path=backtest_storage_directory,
                show_progress=show_progress
            )

        return all_backtests

    def _load_checkpoint_cache(self, storage_directory: str) -> Dict:
        """Load checkpoint file into memory cache once."""
        checkpoint_file = os.path.join(storage_directory, "checkpoints.json")
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, "r") as f:
                return json.load(f)
        return {}

    def _get_checkpointed_from_cache(
        self,
        cache: Dict,
        date_range: BacktestDateRange
    ) -> List[str]:
        """Get checkpointed algorithm IDs from cache."""
        key = (f"{date_range.start_date.isoformat()}_"
               f"{date_range.end_date.isoformat()}")
        return cache.get(key, [])

    def _batch_save_and_checkpoint(
        self,
        backtests: List[Backtest],
        date_range: BacktestDateRange,
        storage_directory: str,
        checkpoint_cache: Dict,
        show_progress: bool = False
    ):
        """Save a batch of backtests and update checkpoint cache."""
        if len(backtests) == 0:
            return

        # Save backtests to disk
        save_backtests_to_directory(
            backtests=backtests,
            directory_path=storage_directory,
            show_progress=show_progress
        )

        # Update cache
        key = (f"{date_range.start_date.isoformat()}_"
               f"{date_range.end_date.isoformat()}")
        if key not in checkpoint_cache:
            checkpoint_cache[key] = []

        for backtest in backtests:
            if backtest.algorithm_id not in checkpoint_cache[key]:
                checkpoint_cache[key].append(backtest.algorithm_id)

        # Write checkpoint file
        checkpoint_file = os.path.join(storage_directory, "checkpoints.json")
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_cache, f, indent=4)

    def _load_backtests_from_cache(
        self,
        checkpoint_cache: Dict,
        date_range: BacktestDateRange,
        storage_directory: str,
        algorithm_ids: List[str]
    ) -> List[Backtest]:
        """Load specific backtests from disk based on checkpoint cache."""
        checkpointed_ids = self._get_checkpointed_from_cache(
            checkpoint_cache, date_range
        )
        backtests = []

        for algo_id in checkpointed_ids:
            if algo_id in algorithm_ids:
                try:
                    backtest_dir = os.path.join(storage_directory, algo_id)
                    if os.path.exists(backtest_dir):
                        backtest = Backtest.open(
                            backtest_dir,
                            backtest_date_ranges=[date_range]
                        )
                        backtests.append(backtest)
                except Exception as e:
                    logger.warning(
                        f"Could not load backtest for {algo_id}: {e}"
                    )

        return backtests

    def _process_strategy_batch(
        self,
        strategies: List,
        backtest_date_range: BacktestDateRange,
        initial_amount: float,
        snapshot_interval: SnapshotInterval,
        risk_free_rate: float,
        market: Optional[str],
        trading_symbol: Optional[str],
        continue_on_error: bool,
        show_progress: bool = False
    ) -> List[Backtest]:
        """
        Process a batch of strategies sequentially.

        Args:
            strategies: List of strategies to process
            backtest_date_range: Date range for backtesting
            initial_amount: Initial portfolio amount
            snapshot_interval: Interval for portfolio snapshots
            risk_free_rate: Risk-free rate for metrics
            market: Optional market filter
            trading_symbol: Optional trading symbol
            continue_on_error: Whether to continue on errors
            show_progress: Whether to show individual progress

        Returns:
            List of completed backtests
        """
        backtests = []

        for strategy in strategies:
            try:
                backtest = self.run_vector_backtest(
                    backtest_date_range=backtest_date_range,
                    initial_amount=initial_amount,
                    strategy=strategy,
                    snapshot_interval=snapshot_interval,
                    risk_free_rate=risk_free_rate,
                    skip_data_sources_initialization=True,
                    market=market,
                    trading_symbol=trading_symbol,
                    continue_on_error=continue_on_error,
                    backtest_storage_directory=None,
                    show_progress=show_progress,
                )
                backtests.append(backtest)

            except Exception as e:
                if continue_on_error:
                    logger.error(
                        f"Error in backtest for {strategy.algorithm_id}: {e}"
                    )
                    continue
                else:
                    raise

        return backtests

    def _save_batch_if_full(
        self,
        batch_buffer: List[Backtest],
        checkpoint_batch_size: int,
        backtest_date_range: BacktestDateRange,
        backtest_storage_directory: str,
        checkpoint_cache: Dict
    ) -> bool:
        """
        Save batch if buffer is full and clear memory.

        Returns:
            True if batch was saved, False otherwise
        """
        if len(batch_buffer) >= checkpoint_batch_size:
            self._batch_save_and_checkpoint(
                batch_buffer,
                backtest_date_range,
                backtest_storage_directory,
                checkpoint_cache,
                show_progress=False
            )
            batch_buffer.clear()
            gc.collect()
            return True
        return False

    def _save_remaining_batch(
        self,
        batch_buffer: List[Backtest],
        backtest_date_range: BacktestDateRange,
        backtest_storage_directory: str,
        checkpoint_cache: Dict
    ):
        """Save any remaining backtests in the buffer."""
        if len(batch_buffer) > 0:
            self._batch_save_and_checkpoint(
                batch_buffer,
                backtest_date_range,
                backtest_storage_directory,
                checkpoint_cache,
                show_progress=False
            )
            batch_buffer.clear()
            gc.collect()

    @staticmethod
    def _run_batch_backtest_worker(args):
        """
        Static worker function for parallel BATCH backtest execution.

        Each worker processes a batch of strategies, reusing the same
        data providers and initialization. This is MUCH more efficient
        than spawning a worker for each individual backtest because:
        - Reduces process creation overhead by 99%
        - Shares data provider initialization across batch
        - Better memory efficiency and cache locality
        - Optimal for 1,000+ backtests

        Args:
            args: Tuple containing (
                strategy_batch,
                backtest_date_range,
                portfolio_configuration,
                snapshot_interval,
                risk_free_rate,
                continue_on_error,
                data_provider_service
            )

        Returns:
            List[Backtest]: List of completed backtest results
        """
        (
            strategy_batch,
            backtest_date_range,
            portfolio_configuration,
            snapshot_interval,
            risk_free_rate,
            continue_on_error,
            data_provider_service,
            show_progress
        ) = args

        vector_backtest_service = VectorBacktestService(
            data_provider_service=data_provider_service
        )

        batch_results = []
        start_date = backtest_date_range.start_date.strftime('%Y-%m-%d')
        end_date = backtest_date_range.end_date.strftime('%Y-%m-%d')
        if show_progress:
            strategy_batch = tqdm(
                strategy_batch,
                colour="green",
                desc=f"Running backtests for {start_date} to {end_date}",
                disable=not show_progress
            )

        for strategy in strategy_batch:
            try:
                backtest_run = vector_backtest_service.run(
                    strategy=strategy,
                    backtest_date_range=backtest_date_range,
                    portfolio_configuration=portfolio_configuration,
                    risk_free_rate=risk_free_rate,
                )
                backtest = Backtest(
                    algorithm_id=strategy.algorithm_id,
                    backtest_runs=[backtest_run],
                    metadata=strategy.metadata if hasattr(
                        strategy, 'metadata') else None,
                    risk_free_rate=risk_free_rate
                )
                batch_results.append(backtest)

            except Exception as e:
                if continue_on_error:
                    logger.error(
                        "Worker error for strategy "
                        f"{strategy.algorithm_id}: {e}"
                    )
                    continue
                else:
                    raise

        return batch_results

    def run_vector_backtest(
        self,
        strategy,
        backtest_date_range: BacktestDateRange = None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        portfolio_configuration: PortfolioConfiguration = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        metadata: Optional[Dict[str, str]] = None,
        risk_free_rate: Optional[float] = None,
        skip_data_sources_initialization: bool = False,
        initial_amount: float = None,
        market: str = None,
        trading_symbol: str = None,
        continue_on_error: bool = False,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
        use_checkpoints: bool = True,
        show_progress: bool = False,
        n_workers: Optional[int] = None,
        batch_size: int = 100,
        checkpoint_batch_size: int = 50,
    ) -> Backtest:
        """
        Run optimized vectorized backtest for a single strategy.

        This method leverages the optimized run_vector_backtests
        implementation, providing the same performance benefits (batching,
        checkpointing, parallel processing) for single strategy backtests.

        Args:
            strategy: The strategy object to backtest.
            backtest_date_range: Single backtest date range to use.
            backtest_date_ranges: List of backtest date ranges to use.
                The strategy will be backtested across all date ranges and
                results will be combined.
            portfolio_configuration: Portfolio configuration to use. If not
                provided, will be created from initial_amount, market, and
                trading_symbol parameters.
            snapshot_interval: The snapshot interval to use for the backtest.
            metadata: Metadata to attach to the backtest report.
            risk_free_rate: The risk-free rate to use for the backtest.
                If not provided, will be fetched automatically.
            skip_data_sources_initialization: Whether to skip data source
                initialization.
            initial_amount: Initial amount to start the backtest with.
                Only used if portfolio_configuration is not provided.
            market: Market to use for the backtest. Only used if
                portfolio_configuration is not provided.
            trading_symbol: Trading symbol to use. Only used if
                portfolio_configuration is not provided.
            continue_on_error: Whether to continue if an error occurs.
            backtest_storage_directory: Directory to save the backtest to.
            use_checkpoints: Whether to use checkpointing to resume interrupted
                backtests. If True, completed backtests will be saved to disk
                and skipped on subsequent runs. If False, the backtest will
                run every time (default: True).
            show_progress: Whether to show progress bars.
            n_workers: Number of parallel workers (None = sequential).
            batch_size: Number of strategies to process in each batch.
            checkpoint_batch_size: Number of backtests before batch save.

        Returns:
            Backtest: Instance of Backtest for the single strategy.
        """
        # Create portfolio configuration if not provided
        if portfolio_configuration is None:

            if initial_amount is None:
                # Try to get from existing portfolio configurations
                portfolio_configurations = \
                    self._portfolio_configuration_service.get_all()

                if portfolio_configurations \
                        and len(portfolio_configurations) > 0:
                    portfolio_configuration = portfolio_configurations[0]
                else:
                    raise OperationalException(
                        "No portfolio configuration provided and no "
                        "initial_amount specified. "
                        "Please provide either a portfolio_configuration "
                        "or initial_amount, "
                        "market, and trading_symbol parameters."
                    )
            else:
                portfolio_configuration = PortfolioConfiguration(
                    identifier="backtest_portfolio",
                    market=market or "BACKTEST",
                    trading_symbol=trading_symbol or "USDT",
                    initial_balance=initial_amount
                )

        # Use the optimized run_vector_backtests method
        backtests = self.run_vector_backtests(
            strategies=[strategy],
            portfolio_configuration=portfolio_configuration,
            backtest_date_range=backtest_date_range,
            backtest_date_ranges=backtest_date_ranges,
            snapshot_interval=snapshot_interval,
            risk_free_rate=risk_free_rate,
            skip_data_sources_initialization=skip_data_sources_initialization,
            show_progress=show_progress,
            continue_on_error=continue_on_error,
            backtest_storage_directory=backtest_storage_directory,
            use_checkpoints=use_checkpoints,
            batch_size=batch_size,
            checkpoint_batch_size=checkpoint_batch_size,
            n_workers=n_workers,
        )

        # Extract the single backtest result
        if backtests and len(backtests) > 0:
            backtest = backtests[0]

            # Add metadata if provided
            if metadata is not None:
                backtest.metadata = metadata
            elif backtest.metadata is None:
                if (hasattr(strategy, 'metadata')
                        and strategy.metadata is not None):
                    backtest.metadata = strategy.metadata
                else:
                    backtest.metadata = {}

            return backtest
        else:
            # Return empty backtest if no results
            return Backtest(
                algorithm_id=strategy.algorithm_id,
                backtest_runs=[],
                risk_free_rate=risk_free_rate or 0.0,
                metadata=metadata or {}
            )

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
