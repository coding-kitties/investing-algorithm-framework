import gc
import json
import logging
import os
import numpy as np
import pandas as pd
import polars as pl
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Union, Optional, Callable

from investing_algorithm_framework.domain import BacktestRun, TimeUnit, \
    OperationalException, BacktestDateRange, Backtest, combine_backtests, \
    generate_backtest_summary_metrics, DataSource, \
    PortfolioConfiguration, tqdm, SnapshotInterval, \
    save_backtests_to_directory
from investing_algorithm_framework.services.data_providers import \
    DataProviderService
from investing_algorithm_framework.services.metrics import \
    create_backtest_metrics, get_risk_free_rate_us
from investing_algorithm_framework.services.portfolios import \
    PortfolioConfigurationService
from .vector_backtest_service import VectorBacktestService


logger = logging.getLogger(__name__)


def _print_progress(message: str, show_progress: bool = True):
    """
    Print progress message with forced flush.

    This ensures output is immediately visible, especially important
    in Jupyter notebooks and long-running processes.

    Args:
        message: The message to print.
        show_progress: Whether to actually print the message.
    """
    if show_progress:
        print(message, flush=True)


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

    def _validate_algorithm_ids(
        self,
        algorithms: List = None,
        strategies: List = None
    ):
        """
        Validate that all strategies have an algorithm id and that they
        are unique.

        Args:
            algorithms (List[Algorithm], optional): The list of algorithms
                to validate.
            strategies (List[TradingStrategy], optional): The list of
                strategies to validate.

        Raises:
            OperationalException: If any strategy does not have an
                algorithm id.
        """
        algorithm_ids = set()

        if algorithms is not None:
            for algorithm in algorithms:

                if not hasattr(algorithm, 'algorithm_id') or \
                        algorithm.algorithm_id is None:
                    raise OperationalException(
                        "All algorithms must have an algorithm_id set "
                        "before backtesting. Please set a unique "
                        "algorithm_id for each algorithm."
                    )
                if algorithm.algorithm_id in algorithm_ids:
                    raise OperationalException(
                        f"Duplicate algorithm_id found: "
                        f"{algorithm.algorithm_id}. "
                        "Please ensure all algorithms have unique "
                        "algorithm_ids."
                    )
                algorithm_ids.add(algorithm.algorithm_id)

        else:

            for strategy in strategies:
                if not hasattr(strategy, 'algorithm_id') or \
                        strategy.algorithm_id is None:
                    raise OperationalException(
                        "All strategies must have an algorithm_id set "
                        "before backtesting. Please set a unique "
                        "algorithm_id for each strategy."
                    )
                if strategy.algorithm_id in algorithm_ids:
                    raise OperationalException(
                        f"Duplicate algorithm_id found: "
                        f"{strategy.algorithm_id}. "
                        "Please ensure all strategies have unique "
                        "algorithm_ids."
                    )

                algorithm_ids.add(strategy.algorithm_id)

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
                for checkpoint in checkpointed:
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
        batch_size: int = 50,
        checkpoint_batch_size: int = 25,
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
                each batch (default: 50).
            checkpoint_batch_size: Number of backtests before batch
                save/checkpoint (default: 25).
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
                _print_progress(
                    "Retrieving risk free rate for metrics calculation ...",
                    show_progress
                )

            risk_free_rate = self._get_risk_free_rate()

            if show_progress:
                _print_progress(
                    f"Retrieved risk free rate of: {risk_free_rate}",
                    show_progress
                )

        # Load checkpoint cache only if checkpointing is enabled
        checkpoint_cache = {}
        if use_checkpoints and backtest_storage_directory is not None:
            checkpoint_cache = self._load_checkpoint_cache(
                backtest_storage_directory
            )

        # Create session cache to track backtests run in this session
        # This ensures we only load backtests from this run, not pre-existing
        # ones in the storage directory
        session_cache = None
        if backtest_storage_directory is not None:
            session_cache = self._create_session_cache()

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

        # Validate algorithm IDs
        self._validate_algorithm_ids(strategies)

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
                _print_progress(
                    "Using checkpoints to skip completed backtests ...",
                    show_progress
                )
                checkpointed_ids = self._get_checkpointed_from_cache(
                    checkpoint_cache, backtest_date_range
                )
                missing_ids = set(active_algorithm_ids) - set(checkpointed_ids)
                strategies_to_run = [
                    s for s in active_strategies
                    if s.algorithm_id in missing_ids
                ]

                # Add checkpointed IDs to session cache so they're included
                # in final loading (they were run in a previous session but
                # are part of the current batch)
                if session_cache is not None:
                    for algo_id in checkpointed_ids:
                        if algo_id in active_algorithm_ids:
                            backtest_path = os.path.join(
                                backtest_storage_directory, algo_id
                            )
                            session_cache["backtests"][algo_id] = backtest_path

                if show_progress and len(checkpointed_ids) > 0:
                    _print_progress(
                        f"Found {len(checkpointed_ids)} "
                        "checkpointed backtests, "
                        f"running {len(strategies_to_run)} new backtests",
                        show_progress
                    )
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
                        _print_progress(
                            f"Running {len(strategies_to_run)} backtests on "
                            f"{n_workers} workers "
                            f"({len(strategy_batches)} batches, "
                            f"~{worker_batch_size} strategies per worker)",
                            show_progress
                        )

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

                        # Track completed batches for periodic cleanup
                        completed_count = 0

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
                                            checkpoint_cache,
                                            session_cache
                                        )

                                # Periodic garbage collection every 10 batches
                                # to prevent memory accumulation
                                completed_count += 1
                                if completed_count % 10 == 0:
                                    gc.collect()

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
                            checkpoint_cache,
                            session_cache
                        )

                else:
                    # Process strategies in batches to manage memory
                    # Split strategies_to_run into batches based on batch_size
                    strategy_batches = [
                        strategies_to_run[i:i + batch_size]
                        for i in range(0, len(strategies_to_run), batch_size)
                    ]

                    if show_progress and len(strategy_batches) > 1:
                        _print_progress(
                            f"Processing {len(strategies_to_run)} "
                            "strategies in "
                            f"{len(strategy_batches)} batches "
                            f"of ~{batch_size} strategies each",
                            show_progress
                        )

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
                                        checkpoint_cache,
                                        session_cache
                                    )

                            # Periodic garbage collection every 5 batches
                            # to prevent memory accumulation
                            if (batch_idx + 1) % 5 == 0:
                                gc.collect()

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
                            checkpoint_cache,
                            session_cache
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

            # Load checkpointed backtests that were SKIPPED (not run in this
            # iteration) if needed for filtering. Only load backtests that
            # were checkpointed from a previous session, not ones that were
            # just run and checkpointed in this session.
            if use_checkpoints and (window_filter_function is not None
                                    or final_filter_function is not None):
                # Get IDs of strategies that were actually run in this
                # iteration
                run_algorithm_ids = set(s.algorithm_id
                                        for s in strategies_to_run)
                # Only load backtests that were SKIPPED
                # (checkpointed, not run)
                skipped_algorithm_ids = [
                    algo_id for algo_id in active_algorithm_ids
                    if algo_id not in run_algorithm_ids
                ]

                if len(skipped_algorithm_ids) > 0:
                    checkpointed_backtests = self._load_backtests_from_cache(
                        checkpoint_cache,
                        backtest_date_range,
                        backtest_storage_directory,
                        skipped_algorithm_ids
                    )
                    all_backtests.extend(checkpointed_backtests)

            # Apply window filter function
            if window_filter_function is not None:
                if show_progress:
                    _print_progress(
                        "Applying window filter function ...",
                        show_progress
                    )
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
                    filtered_algorithm_ids = set(
                        b.algorithm_id for b in filtered_backtests)
                    algorithms_to_mark = [
                        alg_id for alg_id in active_algorithm_ids
                        if alg_id not in filtered_algorithm_ids
                    ]

                    # Update session cache to only include filtered backtests
                    if session_cache is not None:
                        session_cache["backtests"] = {
                            k: v for k, v in session_cache["backtests"].items()
                            if k in filtered_algorithm_ids
                        }

                    # Clear filtered_out flag for backtests that passed
                    # the filter (they may have been filtered out before)
                    for alg_id in filtered_algorithm_ids:
                        backtest_dir = os.path.join(
                            backtest_storage_directory, alg_id
                        )
                        if os.path.exists(backtest_dir):
                            try:
                                backtest = Backtest.open(backtest_dir)
                                if backtest.metadata is not None and \
                                        backtest.metadata.get(
                                            'filtered_out', False
                                        ):
                                    # Clear the filtered_out flag
                                    backtest.metadata['filtered_out'] = False
                                    if 'filtered_out_at_date_range' in \
                                            backtest.metadata:
                                        del backtest.metadata[
                                            'filtered_out_at_date_range'
                                        ]
                                    backtest.save(backtest_dir)
                            except Exception as e:
                                logger.warning(
                                    f"Could not clear filtered_out flag "
                                    f"for backtest {alg_id}: {e}"
                                )

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
            _print_progress(
                "Combining backtests across date ranges ...",
                show_progress
            )

        # After window filtering, active_strategies contains only algorithms
        # that passed all window filters. Use these for final processing.
        active_algorithm_ids_final = set(
            s.algorithm_id for s in active_strategies
        )

        loaded_from_storage = False
        if backtest_storage_directory is not None:
            # Save session cache to disk before final loading
            if session_cache is not None:
                self._save_session_cache(
                    session_cache, backtest_storage_directory
                )

            # Load ONLY from session cache - this ensures we only get
            # backtests from this run, not pre-existing ones in the directory
            all_backtests = self._load_backtests_from_session(
                session_cache,
                active_algorithm_ids_final,
                show_progress=show_progress
            )

            if show_progress and session_cache is not None:
                total_in_session = len(session_cache.get("backtests", {}))
                loaded_count = len(all_backtests)
                if total_in_session > loaded_count:
                    _print_progress(
                        f"Loaded {loaded_count} backtests from session "
                        f"({total_in_session - loaded_count} filtered out)",
                        show_progress
                    )

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
                _print_progress(
                    "Applying final filter function ...",
                    show_progress
                )
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

        # Cleanup session file at the end
        if backtest_storage_directory is not None:
            session_file = os.path.join(
                backtest_storage_directory, "backtest_session.json"
            )
            if os.path.exists(session_file):
                os.remove(session_file)

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
        show_progress: bool = False,
        session_cache: Dict = None
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

        # Update checkpoint cache
        key = (f"{date_range.start_date.isoformat()}_"
               f"{date_range.end_date.isoformat()}")
        if key not in checkpoint_cache:
            checkpoint_cache[key] = []

        for backtest in backtests:
            if backtest.algorithm_id not in checkpoint_cache[key]:
                checkpoint_cache[key].append(backtest.algorithm_id)

        # Write checkpoint file with forced flush to disk
        checkpoint_file = os.path.join(storage_directory, "checkpoints.json")
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_cache, f, indent=4)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Update session cache if provided
        if session_cache is not None:
            self._update_session_cache(
                backtests, storage_directory, session_cache
            )

    def _create_session_cache(self) -> Dict:
        """
        Create a new session cache to track backtests run in this session.

        Returns:
            Dict: Empty session cache structure
        """
        return {
            "session_id": datetime.now(timezone.utc).isoformat(),
            "backtests": {}  # algorithm_id -> backtest_path
        }

    def _update_session_cache(
        self,
        backtests: List[Backtest],
        storage_directory: str,
        session_cache: Dict
    ):
        """
        Update session cache with newly saved backtests.

        Args:
            backtests: List of backtests that were saved
            storage_directory: Directory where backtests are stored
            session_cache: Session cache to update
        """
        for backtest in backtests:
            algorithm_id = backtest.algorithm_id
            backtest_path = os.path.join(storage_directory, algorithm_id)
            session_cache["backtests"][algorithm_id] = backtest_path

    def _save_session_cache(
        self,
        session_cache: Dict,
        storage_directory: str
    ):
        """
        Save session cache to disk.

        Args:
            session_cache: Session cache to save
            storage_directory: Directory to save the session file
        """
        session_file = os.path.join(
            storage_directory, "backtest_session.json"
        )
        with open(session_file, "w") as f:
            json.dump(session_cache, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

    def _load_backtests_from_session(
        self,
        session_cache: Dict,
        active_algorithm_ids: set = None,
        show_progress: bool = False
    ) -> List[Backtest]:
        """
        Load backtests from the current session cache.

        This method efficiently loads only the backtests that were run
        in the current session, avoiding loading pre-existing backtests
        from the storage directory.

        Args:
            session_cache: Session cache containing backtest paths
            active_algorithm_ids: Optional set of algorithm IDs to filter by
                (e.g., those that passed window filters)
            show_progress: Whether to show progress bar

        Returns:
            List[Backtest]: List of backtests from the current session
        """
        backtests = []
        backtest_paths = session_cache.get("backtests", {})

        # Filter by active_algorithm_ids if provided
        if active_algorithm_ids is not None:
            paths_to_load = {
                alg_id: path for alg_id, path in backtest_paths.items()
                if alg_id in active_algorithm_ids
            }
        else:
            paths_to_load = backtest_paths

        items = list(paths_to_load.items())

        for algorithm_id, backtest_path in tqdm(
            items,
            colour="green",
            desc="Loading session backtests",
            disable=not show_progress
        ):
            try:
                if os.path.exists(backtest_path):
                    backtest = Backtest.open(backtest_path)
                    backtests.append(backtest)
                else:
                    logger.warning(
                        f"Backtest path does not exist: {backtest_path}"
                    )
            except Exception as e:
                logger.warning(
                    f"Could not load backtest {algorithm_id} "
                    f"from {backtest_path}: {e}"
                )

        return backtests

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
        checkpoint_cache: Dict,
        session_cache: Dict = None
    ) -> bool:
        """
        Save batch if buffer is full and clear memory.

        Args:
            batch_buffer: List of backtests to potentially save.
            checkpoint_batch_size: Threshold for saving.
            backtest_date_range: The backtest date range.
            backtest_storage_directory: Directory to save to.
            checkpoint_cache: Checkpoint cache to update.
            session_cache: Session cache to track backtests from this run.

        Returns:
            True if batch was saved, False otherwise
        """
        if len(batch_buffer) >= checkpoint_batch_size:
            self._batch_save_and_checkpoint(
                batch_buffer,
                backtest_date_range,
                backtest_storage_directory,
                checkpoint_cache,
                show_progress=False,
                session_cache=session_cache
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
        checkpoint_cache: Dict,
        session_cache: Dict = None
    ):
        """
        Save any remaining backtests in the buffer.

        Args:
            batch_buffer: List of backtests to save.
            backtest_date_range: The backtest date range.
            backtest_storage_directory: Directory to save to.
            checkpoint_cache: Checkpoint cache to update.
            session_cache: Session cache to track backtests from this run.
        """
        if len(batch_buffer) > 0:
            self._batch_save_and_checkpoint(
                batch_buffer,
                backtest_date_range,
                backtest_storage_directory,
                checkpoint_cache,
                show_progress=False,
                session_cache=session_cache
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
        batch_size: int = 50,
        checkpoint_batch_size: int = 25,
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

    def run_backtests(
        self,
        algorithms: List,
        context,
        trade_stop_loss_service,
        trade_take_profit_service,
        backtest_date_range: BacktestDateRange = None,
        backtest_date_ranges: List[BacktestDateRange] = None,
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
        use_checkpoints: bool = False,
        batch_size: int = 50,
        checkpoint_batch_size: int = 25,
    ) -> List[Backtest]:
        """
        Run event-driven backtests for multiple algorithms with optional
        checkpointing, batching, and storage.

        This method mirrors run_vector_backtests but for event-driven
        backtesting where strategies' `on_run` methods are called at
        each scheduled time step.

        Args:
            algorithms: List of algorithms to backtest.
            context: The app context for the event loop service.
            trade_stop_loss_service: Service for handling stop loss orders.
            trade_take_profit_service: Service for handling take profit orders.
            backtest_date_range: Single backtest date range to use.
            backtest_date_ranges: List of backtest date ranges to use.
            risk_free_rate: Risk-free rate for backtest metrics.
            skip_data_sources_initialization: Whether to skip data
                source initialization.
            show_progress: Whether to show progress bars.
            continue_on_error: Whether to continue on errors.
            window_filter_function: Filter function applied after each
                date range.
            final_filter_function: Filter function applied at the end.
            backtest_storage_directory: Directory to store backtests.
            use_checkpoints: Whether to use checkpointing to resume
                interrupted backtests.
            batch_size: Number of algorithms to process in each batch.
            checkpoint_batch_size: Number of backtests before batch
                save/checkpoint.

        Returns:
            List[Backtest]: List of backtest results.
        """
        from .event_backtest_service import EventBacktestService
        from investing_algorithm_framework.app.eventloop import \
            EventLoopService
        from investing_algorithm_framework.services import \
            BacktestTradeOrderEvaluator

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

        # Collect all data sources from all algorithms
        data_sources = []
        for algorithm in algorithms:
            if hasattr(algorithm, 'data_sources') and algorithm.data_sources:
                data_sources.extend(algorithm.data_sources)

        # Get risk-free rate if not provided
        if risk_free_rate is None:
            if show_progress:
                _print_progress(
                    "Retrieving risk free rate for metrics calculation ...",
                    show_progress
                )
            risk_free_rate = self._get_risk_free_rate()
            if show_progress:
                _print_progress(
                    f"Retrieved risk free rate of: {risk_free_rate}",
                    show_progress
                )

        # Load checkpoint cache only if checkpointing is enabled
        checkpoint_cache = {}
        if use_checkpoints and backtest_storage_directory is not None:
            checkpoint_cache = self._load_checkpoint_cache(
                backtest_storage_directory
            )

        # Create session cache to track backtests run in this session
        session_cache = None
        if backtest_storage_directory is not None:
            session_cache = self._create_session_cache()

        # Handle single date range case - convert to list
        if backtest_date_range is not None:
            backtest_date_ranges = [backtest_date_range]

        # Sort and deduplicate date ranges
        unique_date_ranges = set(backtest_date_ranges)
        backtest_date_ranges = sorted(
            unique_date_ranges, key=lambda x: x.start_date
        )

        # Track all backtests across date ranges
        # Use id(algorithm) as key to handle multiple algorithms
        # with the same algorithm_id (each algorithm object is unique)
        backtests_by_algorithm = {}
        algorithm_id_map = {}  # Maps id(alg) -> algorithm_id for final output
        active_algorithms = algorithms.copy()

        # Build algorithm_id_map for tracking
        for alg in algorithms:
            alg_id = alg.algorithm_id if (
                hasattr(alg, 'algorithm_id')
            ) else alg.id
            algorithm_id_map[id(alg)] = alg_id

        # Determine if this is a simple single backtest case
        is_single_backtest = (
            len(algorithms) == 1 and len(backtest_date_ranges) == 1
        )

        for backtest_date_range in tqdm(
            backtest_date_ranges,
            colour="green",
            desc="Running event backtests for all date ranges",
            disable=not show_progress or is_single_backtest
        ):
            if not skip_data_sources_initialization:
                self.initialize_data_sources_backtest(
                    data_sources,
                    backtest_date_range,
                    show_progress=show_progress
                )

            active_algorithm_ids = []
            for alg in active_algorithms:
                alg_id = alg.algorithm_id if hasattr(
                    alg, 'algorithm_id'
                ) else alg.id
                active_algorithm_ids.append(alg_id)

            # Only check for checkpoints if use_checkpoints is True
            if use_checkpoints:
                _print_progress(
                    "Using checkpoints to "
                    "skip completed backtests ...",
                    show_progress
                )
                checkpointed_ids = self._get_checkpointed_from_cache(
                    checkpoint_cache, backtest_date_range
                )
                missing_ids = set(active_algorithm_ids) - set(checkpointed_ids)
                algorithms_to_run = [
                    alg for alg in active_algorithms
                    if (alg.algorithm_id if hasattr(
                        alg, 'algorithm_id'
                    ) else alg.id) in missing_ids
                ]

                # Add checkpointed IDs to session cache
                if session_cache is not None:
                    for algo_id in checkpointed_ids:
                        if algo_id in active_algorithm_ids:
                            backtest_path = os.path.join(
                                backtest_storage_directory, algo_id
                            )
                            session_cache["backtests"][algo_id] = backtest_path

                if show_progress and len(checkpointed_ids) > 0:
                    _print_progress(
                        f"Found {len(checkpointed_ids)} checkpointed "
                        f"backtests, "
                        f"running {len(algorithms_to_run)} new backtests",
                        show_progress
                    )
            else:
                algorithms_to_run = active_algorithms

            all_backtests = []
            batch_buffer = []

            if len(algorithms_to_run) > 0:
                # Process algorithms in batches
                algorithm_batches = [
                    algorithms_to_run[i:i + batch_size]
                    for i in range(0, len(algorithms_to_run), batch_size)
                ]

                if show_progress and len(algorithm_batches) > 1:
                    _print_progress(
                        f"Processing {len(algorithms_to_run)} "
                        f"algorithms in "
                        f"{len(algorithm_batches)} batches "
                        f"of ~{batch_size} each",
                        show_progress
                    )

                for batch_idx, algorithm_batch in enumerate(tqdm(
                    algorithm_batches,
                    colour="green",
                    desc="Processing algorithm batches",
                    disable=not show_progress or len(algorithm_batches) == 1
                )):
                    for algorithm in algorithm_batch:
                        algorithm_id = (
                            algorithm.algorithm_id
                            if hasattr(algorithm, 'algorithm_id')
                            else algorithm.id
                        )

                        try:
                            # Create event backtest service
                            event_backtest_service = EventBacktestService(
                                data_provider_service=(
                                    self._data_provider_service
                                ),
                                order_service=self._order_service,
                                portfolio_service=self._portfolio_service,
                                portfolio_snapshot_service=(
                                    self._portfolio_snapshot_service
                                ),
                                position_repository=self._position_repository,
                                trade_service=self._trade_service,
                                configuration_service=(
                                    self._configuration_service
                                ),
                                portfolio_configuration_service=(
                                    self._portfolio_configuration_service
                                ),
                            )

                            # Create event loop service
                            event_loop_service = EventLoopService(
                                configuration_service=(
                                    self._configuration_service
                                ),
                                portfolio_snapshot_service=(
                                    self._portfolio_snapshot_service
                                ),
                                context=context,
                                order_service=self._order_service,
                                portfolio_service=self._portfolio_service,
                                data_provider_service=(
                                    self._data_provider_service
                                ),
                                trade_service=self._trade_service,
                            )

                            # Create trade order evaluator
                            trade_order_evaluator = (
                                BacktestTradeOrderEvaluator(
                                    trade_service=self._trade_service,
                                    order_service=self._order_service,
                                    trade_stop_loss_service=(
                                        trade_stop_loss_service
                                    ),
                                    trade_take_profit_service=(
                                        trade_take_profit_service
                                    ),
                                    configuration_service=(
                                        self._configuration_service
                                    )
                                )
                            )

                            # Generate schedule
                            schedule = (
                                event_backtest_service.generate_schedule(
                                    algorithm.strategies,
                                    algorithm.tasks,
                                    backtest_date_range.start_date,
                                    backtest_date_range.end_date
                                )
                            )

                            # Initialize and run
                            event_loop_service.initialize(
                                algorithm=algorithm,
                                trade_order_evaluator=trade_order_evaluator
                            )
                            # Show progress for single backtest,
                            # hide for batches
                            event_loop_service.start(
                                schedule=schedule,
                                show_progress=(
                                    show_progress and is_single_backtest
                                )
                            )

                            # Create backtest
                            backtest = (
                                event_backtest_service.create_backtest(
                                    algorithm=algorithm,
                                    backtest_date_range=backtest_date_range,
                                    number_of_runs=(
                                        event_loop_service.total_number_of_runs
                                    ),
                                    risk_free_rate=risk_free_rate,
                                )
                            )

                            # Add metadata
                            if (hasattr(algorithm, 'metadata')
                                    and algorithm.metadata):
                                backtest.metadata = algorithm.metadata
                            else:
                                backtest.metadata = {}

                            # Store with algorithm object id for tracking
                            backtest._algorithm_obj_id = id(algorithm)
                            all_backtests.append(backtest)
                            batch_buffer.append(backtest)

                            # Save batch if full
                            if backtest_storage_directory is not None:
                                self._save_batch_if_full(
                                    batch_buffer,
                                    checkpoint_batch_size,
                                    backtest_date_range,
                                    backtest_storage_directory,
                                    checkpoint_cache,
                                    session_cache
                                )

                        except Exception as e:
                            if continue_on_error:
                                logger.error(
                                    f"Error in backtest for "
                                    f"{algorithm_id}: {e}"
                                )
                                continue
                            else:
                                raise

                    # Periodic garbage collection
                    if (batch_idx + 1) % 5 == 0:
                        gc.collect()

                # Save remaining batch
                if backtest_storage_directory is not None:
                    self._save_remaining_batch(
                        batch_buffer,
                        backtest_date_range,
                        backtest_storage_directory,
                        checkpoint_cache,
                        session_cache
                    )

            # Store backtests in memory when no storage directory provided
            if backtest_storage_directory is None:
                for backtest in all_backtests:
                    # Use algorithm object id if available,
                    # otherwise algorithm_id
                    key = (getattr(backtest, '_algorithm_obj_id', None)
                           or backtest.algorithm_id)
                    if key not in backtests_by_algorithm:
                        backtests_by_algorithm[key] = []
                    backtests_by_algorithm[key].append(backtest)

            # Load checkpointed backtests that were SKIPPED (not run in this
            # iteration) if needed for filtering. Only load backtests that
            # were checkpointed from a previous session, not ones that were
            # just run and checkpointed in this session.
            if use_checkpoints and (window_filter_function is not None
                                    or final_filter_function is not None):
                # Get IDs of algorithms that were actually run in this
                # iteration
                run_algorithm_ids = set(
                    (alg.algorithm_id if hasattr(alg, 'algorithm_id')
                     else alg.id)
                    for alg in algorithms_to_run
                )
                # Only load backtests that were SKIPPED
                # (checkpointed, not run)
                skipped_algorithm_ids = [
                    algo_id for algo_id in active_algorithm_ids
                    if algo_id not in run_algorithm_ids
                ]

                if len(skipped_algorithm_ids) > 0:
                    checkpointed_backtests = self._load_backtests_from_cache(
                        checkpoint_cache,
                        backtest_date_range,
                        backtest_storage_directory,
                        skipped_algorithm_ids
                    )
                    all_backtests.extend(checkpointed_backtests)

            # Apply window filter function
            if window_filter_function is not None:
                if show_progress:
                    _print_progress(
                        "Applying window filter function ...",
                        show_progress
                    )
                filtered_backtests = window_filter_function(
                    all_backtests, backtest_date_range
                )
                filtered_ids = set(b.algorithm_id for b in filtered_backtests)
                active_algorithms = [
                    alg for alg in active_algorithms
                    if (alg.algorithm_id if hasattr(alg, 'algorithm_id')
                        else alg.id) in filtered_ids
                ]

                # Update tracking
                if backtest_storage_directory is None:
                    algorithms_to_remove = [
                        alg_id for alg_id in backtests_by_algorithm.keys()
                        if alg_id not in filtered_ids
                    ]
                    for alg_id in algorithms_to_remove:
                        del backtests_by_algorithm[alg_id]
                else:
                    # When using storage, update filtered_out metadata
                    algorithms_to_mark = [
                        alg_id for alg_id in active_algorithm_ids
                        if alg_id not in filtered_ids
                    ]

                    # Update session cache to only include filtered backtests
                    if session_cache is not None:
                        session_cache["backtests"] = {
                            k: v for k, v in session_cache["backtests"].items()
                            if k in filtered_ids
                        }

                    # Clear filtered_out flag for backtests that passed
                    # the filter (they may have been filtered out before)
                    for alg_id in filtered_ids:
                        backtest_dir = os.path.join(
                            backtest_storage_directory, alg_id
                        )
                        if os.path.exists(backtest_dir):
                            try:
                                backtest = Backtest.open(backtest_dir)
                                if backtest.metadata is not None and \
                                        backtest.metadata.get(
                                            'filtered_out', False
                                        ):
                                    backtest.metadata['filtered_out'] = False
                                    if 'filtered_out_at_date_range' in \
                                            backtest.metadata:
                                        del backtest.metadata[
                                            'filtered_out_at_date_range'
                                        ]
                                    backtest.save(backtest_dir)
                            except Exception as e:
                                logger.warning(
                                    f"Could not clear filtered_out flag "
                                    f"for backtest {alg_id}: {e}"
                                )

                    # Mark filtered-out backtests with metadata flag
                    for alg_id in algorithms_to_mark:
                        backtest_dir = os.path.join(
                            backtest_storage_directory, alg_id
                        )
                        if os.path.exists(backtest_dir):
                            try:
                                backtest = Backtest.open(backtest_dir)
                                start_date = backtest_date_range.start_date
                                end_date = backtest_date_range.end_date
                                date_key = (
                                    f"{start_date.isoformat()}_"
                                    f"{end_date.isoformat()}"
                                )
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

        # Combine backtests
        if show_progress:
            _print_progress(
                "Combining backtests across date ranges ...",
                show_progress
            )

        active_algorithm_ids_final = set()
        for alg in active_algorithms:
            alg_id = alg.algorithm_id if hasattr(alg, 'algorithm_id') \
                else alg.id
            active_algorithm_ids_final.add(alg_id)

        loaded_from_storage = False
        if backtest_storage_directory is not None:
            # Save session cache to disk before final loading
            if session_cache is not None:
                self._save_session_cache(
                    session_cache, backtest_storage_directory
                )

            # Load ONLY from session cache - this ensures we only get
            # backtests from this run, not pre-existing ones
            all_backtests = self._load_backtests_from_session(
                session_cache,
                active_algorithm_ids_final,
                show_progress=show_progress
            )
            loaded_from_storage = True
        else:
            combined_backtests = []
            for algorithm_id, backtests_list in backtests_by_algorithm.items():
                if len(backtests_list) == 1:
                    combined_backtests.append(backtests_list[0])
                else:
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
                _print_progress(
                    "Applying final filter function ...",
                    show_progress
                )
            all_backtests = final_filter_function(all_backtests)

        # Save if not loaded from storage
        if (backtest_storage_directory is not None
                and not loaded_from_storage):
            save_backtests_to_directory(
                backtests=all_backtests,
                directory_path=backtest_storage_directory,
                show_progress=show_progress
            )

        # Cleanup session file at the end
        if backtest_storage_directory is not None:
            session_file = os.path.join(
                backtest_storage_directory, "backtest_session.json"
            )
            if os.path.exists(session_file):
                os.remove(session_file)

        return all_backtests

    def run_backtest(
        self,
        algorithm,
        backtest_date_range: BacktestDateRange,
        context,
        trade_stop_loss_service,
        trade_take_profit_service,
        backtest_date_ranges: List[BacktestDateRange] = None,
        risk_free_rate: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
        skip_data_sources_initialization: bool = False,
        backtest_storage_directory: Optional[Union[str, Path]] = None,
        use_checkpoints: bool = False,
        show_progress: bool = True,
        initial_amount: float = None,
        market: str = None,
        trading_symbol: str = None,
    ) -> tuple:
        """
        Run an event-driven backtest for a single algorithm.

        This method leverages the run_backtests implementation,
        providing the same features (checkpointing, storage) for
        single algorithm backtests.

        Args:
            algorithm: The algorithm to backtest.
            backtest_date_range: Single backtest date range to use.
            context: The app context for the event loop service.
            trade_stop_loss_service: Service for handling stop loss orders.
            trade_take_profit_service: Service for handling take profit orders.
            backtest_date_ranges: List of backtest date ranges to use.
                If provided, algorithm will be backtested across all date
                ranges and results will be combined.
            risk_free_rate: The risk-free rate for calculating metrics.
            metadata: Metadata to attach to the backtest report.
            skip_data_sources_initialization: Whether to skip data source
                initialization.
            backtest_storage_directory: Directory to save the backtest to.
            use_checkpoints: Whether to use checkpointing.
            show_progress: Whether to show progress bars.
            initial_amount: Initial amount (for compatibility, not used here
                as algorithm already has portfolio config).
            market: Market (for compatibility).
            trading_symbol: Trading symbol (for compatibility).

        Returns:
            Tuple[Backtest, Dict]: A tuple containing:
                - Backtest: Instance of Backtest containing the results.
                - Dict: Empty dict (for compatibility with event loop history).
        """
        # Use run_backtests with single algorithm
        backtests = self.run_backtests(
            algorithms=[algorithm],
            context=context,
            trade_stop_loss_service=trade_stop_loss_service,
            trade_take_profit_service=trade_take_profit_service,
            backtest_date_range=backtest_date_range,
            backtest_date_ranges=backtest_date_ranges,
            risk_free_rate=risk_free_rate,
            skip_data_sources_initialization=skip_data_sources_initialization,
            show_progress=show_progress,
            continue_on_error=False,
            backtest_storage_directory=backtest_storage_directory,
            use_checkpoints=use_checkpoints,
        )

        # Extract the single backtest result
        if backtests and len(backtests) > 0:
            backtest = backtests[0]

            # Add metadata if provided
            if metadata is not None:
                backtest.metadata = metadata
            elif backtest.metadata is None:
                if hasattr(algorithm, 'metadata') and algorithm.metadata:
                    backtest.metadata = algorithm.metadata
                else:
                    backtest.metadata = {}

            return backtest, {}
        else:
            # Return empty backtest if no results
            algorithm_id = (
                algorithm.algorithm_id
                if hasattr(algorithm, 'algorithm_id')
                else algorithm.id
            )
            return Backtest(
                algorithm_id=algorithm_id,
                backtest_runs=[],
                risk_free_rate=risk_free_rate or 0.0,
                metadata=metadata or {}
            ), {}

    def create_ohlcv_permutation(
        self,
        data: Union[pd.DataFrame, pl.DataFrame],
        start_index: int = 0,
        seed: int | None = None,
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Create a permuted OHLCV dataset by shuffling relative price moves.

        Args:
            data: A single OHLCV DataFrame (pandas or polars)
                with columns ['Open', 'High', 'Low', 'Close', 'Volume'].
                For pandas: Datetime can be either
                index or a 'Datetime' column. For polars: Datetime
                must be a 'Datetime' column.
            start_index: Index at which the permutation should begin
                (bars before remain unchanged).
            seed: Random seed for reproducibility.

        Returns:
            DataFrame of the same type (pandas or polars) with
                permuted OHLCV values, preserving the datetime
                structure (index vs column) of the input.
        """

        if start_index < 0:
            raise OperationalException("start_index must be >= 0")

        if seed is None:
            seed = np.random.randint(0, 1_000_000)

        np.random.seed(seed)
        is_polars = isinstance(data, pl.DataFrame)

        # Normalize input to pandas
        if is_polars:
            has_datetime_col = "Datetime" in data.columns
            ohlcv_pd = data.to_pandas().copy()
            if has_datetime_col:
                time_index = pd.to_datetime(ohlcv_pd["Datetime"])
            else:
                time_index = np.arange(len(ohlcv_pd))
        else:
            has_datetime_col = "Datetime" in data.columns
            if isinstance(data.index, pd.DatetimeIndex):
                time_index = data.index
            elif has_datetime_col:
                time_index = pd.to_datetime(data["Datetime"])
            else:
                time_index = np.arange(len(data))
            ohlcv_pd = data.copy()

        # Prepare data
        n_bars = len(ohlcv_pd)
        perm_index = start_index + 1
        perm_n = n_bars - perm_index

        # Ensure all OHLCV values are positive before taking log
        # Replace non-positive values with NaN and forward fill
        ohlcv_cols = ["Open", "High", "Low", "Close"]
        for col in ohlcv_cols:
            ohlcv_pd.loc[ohlcv_pd[col] <= 0, col] = np.nan

        # Forward fill NaN values to maintain data continuity
        ohlcv_pd[ohlcv_cols] = ohlcv_pd[ohlcv_cols].ffill()

        # If there are still NaN values at the start, backward fill
        ohlcv_pd[ohlcv_cols] = ohlcv_pd[ohlcv_cols].bfill()

        # If all values are still invalid, raise an error
        if ohlcv_pd[ohlcv_cols].isna().any().any():
            raise ValueError(
                "OHLCV data contains invalid (zero or negative) values "
                "that cannot be processed"
            )

        log_bars = np.log(ohlcv_pd[ohlcv_cols])

        # Start bar
        start_bar = log_bars.iloc[start_index].to_numpy()

        # Relative series
        rel_open = (log_bars["Open"] - log_bars["Close"].shift()).to_numpy()
        rel_high = (log_bars["High"] - log_bars["Open"]).to_numpy()
        rel_low = (log_bars["Low"] - log_bars["Open"]).to_numpy()
        rel_close = (log_bars["Close"] - log_bars["Open"]).to_numpy()

        # Shuffle independently
        idx = np.arange(perm_n)
        rel_high = rel_high[perm_index:][np.random.permutation(idx)]
        rel_low = rel_low[perm_index:][np.random.permutation(idx)]
        rel_close = rel_close[perm_index:][np.random.permutation(idx)]
        rel_open = rel_open[perm_index:][np.random.permutation(idx)]

        # Build permuted OHLC
        perm_bars = np.zeros((n_bars, 4))
        perm_bars[:start_index] = log_bars.iloc[:start_index].to_numpy()
        perm_bars[start_index] = start_bar

        for i in range(perm_index, n_bars):
            k = i - perm_index
            perm_bars[i, 0] = perm_bars[i - 1, 3] + rel_open[k]   # Open
            perm_bars[i, 1] = perm_bars[i, 0] + rel_high[k]       # High
            perm_bars[i, 2] = perm_bars[i, 0] + rel_low[k]        # Low
            perm_bars[i, 3] = perm_bars[i, 0] + rel_close[k]      # Close

        perm_bars = np.exp(perm_bars)

        # Rebuild OHLCV
        perm_df = pd.DataFrame(
            perm_bars,
            columns=["Open", "High", "Low", "Close"],
        )
        perm_df["Volume"] = ohlcv_pd["Volume"].values

        # Restore datetime structure
        if is_polars:
            if has_datetime_col:
                perm_df.insert(0, "Datetime", time_index)
            return pl.from_pandas(perm_df)
        else:
            if isinstance(data.index, pd.DatetimeIndex):
                perm_df.index = time_index
                perm_df.index.name = data.index.name or "Datetime"
            elif has_datetime_col:
                perm_df.insert(0, "Datetime", time_index)
            return perm_df
