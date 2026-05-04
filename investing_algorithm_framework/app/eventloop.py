from datetime import datetime, timedelta, timezone
from time import sleep
from typing import List, Set, Dict, FrozenSet, Tuple, Optional, Type
from logging import getLogger

import polars as pl

from investing_algorithm_framework.domain import Environment, ENVIRONMENT, \
    OrderStatus, DataSource, DataType, tqdm, \
    TradeStatus, SNAPSHOT_INTERVAL, SnapshotInterval, OperationalException, \
    LAST_SNAPSHOT_DATETIME, INDEX_DATETIME
from investing_algorithm_framework.services import TradeOrderEvaluator
from investing_algorithm_framework.services.pipeline import PipelineEngine

from .algorithm import Algorithm
from .strategy import TradingStrategy

logger = getLogger("investing_algorithm_framework")


class EventLoopService:
    """
    A service that manages the event loop for the trading bot.
    This service is responsible for running the trading strategy and handling
    events in its lifecycle, such as pending orders changes, stop loss changes,
    take profit changes, and price data updates.

    The event loop runs strategies in a so called interation, which consists
    out of various tasks. An iteration consists out of the following tasks:

        - Collect all strategies and tasks that need to be
            run (overdue on schedule)
        - Collect all market data for the strategies
        - Check pending orders, stop losses, and take profits
        - Run all tasks
        - Run all strategies
        - Run all on_strategy_run hooks
        - Snapshot the portfolios based on the defined snapshot interval

    The goal of this service is to provide a way to run the trading in the
    most efficient way possible in both live trading and backtesting. This
    is achieved by running strategies and tasks in a loop, where each
    iteration checks which strategies and tasks are due to run based on their
    defined intervals and time units (seconds, minutes, hours). The next run
    times for each strategy are initialized to the current time in UTC.
    The service also collects all data configurations from the strategies and
    tasks, and runs them in a single iteration to avoid multiple calls to the
    data provider service, which can be expensive in terms of performance.
    """

    def __init__(
        self,
        context,
        order_service,
        trade_service,
        portfolio_service,
        configuration_service,
        data_provider_service,
        portfolio_snapshot_service
    ):
        """
        Initializes the event loop service with the provided algorithm.

        Args:
            order_service: The service responsible for managing orders.
            portfolio_service: The service responsible for managing portfolios.
            configuration_service: The service responsible for configuration.
        """
        self.tasks = []
        self.context = context
        self._algorithm = None
        self.strategies = []
        self._strategies_lookup = {}
        self._snapshots = []
        self._tasks_lookup = {}
        self._order_service = order_service
        self._trade_service = trade_service
        self._portfolio_service = portfolio_service
        self._configuration_service = configuration_service
        self._data_provider_service = data_provider_service
        self._trade_order_evaluator = None
        self._portfolio_snapshot_service = portfolio_snapshot_service
        self.data_sources = set()
        self.next_run_times = {}
        self.history = {}
        self._pipeline_engine = PipelineEngine()

        # Per (strategy_id, pipeline_cls) cache of the most recent
        # universe-refresh: (refresh_at, frozen surviving-symbol set).
        # Populated when a pipeline declares
        # ``refresh_universe_every`` so the engine can skip re-running
        # the universe filter every bar.
        self._pipeline_universe_cache: Dict[
            Tuple[str, Type], Tuple[datetime, FrozenSet[str]]
        ] = {}
        # One-shot flag: live-mode envelope validation runs once per
        # process. Reset by ``cleanup`` so a new run re-validates.
        self._pipelines_live_validated: bool = False

    @staticmethod
    def _get_data_sources_for_iteration(
        strategy_data_sources
    ) -> Set[DataSource]:
        """
        Return a list of data sources that need to be fetched for the
        current iteration based on the strategies.

        Args:
            strategy_data_sources: List of data sources defined
                in the strategies.
        Returns:
            Set[DataSource]: A set of data sources that need to
                be fetched.
        """
        data_sources = set(strategy_data_sources)
        return data_sources

    def _get_pending_orders_and_trades_data_for_iteration(
        self, pending_order, open_trades, date
    ) -> Dict:
        """
        Returns a set of data sources that need to be fetched for the
        current iteration based on the pending orders and open trades.

        Args:
            pending_order: List of pending orders.
            open_trades: List of open trades.
            date: The current date for which the data is being fetched.

        Returns:
            Set[DataSource]: A set of data sources that need to be fetched.
        """
        symbol_set = set()
        data_sources = set()
        data = {}

        for order in pending_order:
            if order.symbol not in symbol_set:
                data_sources.add(
                    DataSource(
                        symbol=order.symbol,
                        data_type=DataType.TICKER
                    )
                )
                symbol_set.add(order.symbol)

        for trade in open_trades:

            if trade.symbol not in symbol_set:
                data_sources.add(
                    DataSource(symbol=trade.symbol, data_type=DataType.TICKER))
                symbol_set.add(trade.symbol)

        for symbol in symbol_set:
            data[symbol] = self._data_provider_service\
                .get_ohlcv_data(
                    symbol=symbol, date=date
                )
        return data

    def _get_strategies(
        self, strategy_ids: List[str]
    ) -> List[TradingStrategy]:
        """
        Returns a list of strategies based on the provided strategy IDs.

        Args:
            strategy_ids: A list of strategy IDs to retrieve.

        Returns:
            List[TradingStrategy]: A list of strategies matching the
                provided IDs.
        """

        if not strategy_ids:
            return self.strategies

        return [
            self._strategies_lookup[strategy_id]
            for strategy_id in strategy_ids
        ]

    def _get_due_strategies(self, current_datetime=None):
        """
        Checks which strategies are due to run based on their defined intervals

        Args:
            current_datetime: Optional; the datetime to check against.
                If None, uses the current datetime in UTC.

        Returns:
            List[TradingStrategy]: A list of strategies that are due to run.
        """
        due = []

        if current_datetime is None:
            current_datetime = datetime.now(timezone.utc)

        for strategy in self.strategies:
            time_unit = strategy.time_unit
            interval = strategy.interval
            interval = timedelta(
                minutes=time_unit.amount_of_minutes * interval
            )

            if current_datetime >= \
                    self.next_run_times[strategy.strategy_id]["next_run"]:
                due.append(strategy)
                self.next_run_times[strategy.strategy_id]["next_run"] = \
                    current_datetime + interval

        return due

    def _snapshot(
        self,
        current_datetime,
        open_orders,
        created_orders
    ):
        """
        Takes a snapshot of the current state of the portfolios and trades.
        This method is called based on the defined snapshot interval in the
        configuration service. It creates a snapshot of the portfolio and
        appends it to the snapshots list.

        The function accepts the current datetime, open orders,
        open trades, and created orders as parameters. The reason why
        the orders and trades are passed is for efficiency, as we
        do not want to fetch them again from the database if they are
        already available in memory.

        Args:
            current_datetime: The current datetime in UTC.
            open_orders: List of open orders.
            created_orders: List of created orders.
        """
        snapshot_interval = self._configuration_service\
            .config[SNAPSHOT_INTERVAL]
        portfolio = self._portfolio_service.get_all()[0]
        if SnapshotInterval.STRATEGY_ITERATION.equals(snapshot_interval):
            snapshot = self._portfolio_snapshot_service.create_snapshot(
                created_at=current_datetime,
                portfolio=portfolio,
                open_orders=open_orders,
                created_orders=created_orders,
                save=False,
            )
            self._snapshots.append(snapshot)
            self._configuration_service.add_value(
                LAST_SNAPSHOT_DATETIME, current_datetime
            )
        elif SnapshotInterval.DAILY.equals(snapshot_interval):
            last_snapshot_datetime = self._configuration_service.config[
                LAST_SNAPSHOT_DATETIME
            ]

            # Check if the time difference is greater than 24 hours
            if last_snapshot_datetime is None or \
                    (current_datetime - last_snapshot_datetime)\
                    .total_seconds() >= 86400:
                snapshot = self._portfolio_snapshot_service.create_snapshot(
                    created_at=current_datetime,
                    portfolio=portfolio,
                    open_orders=open_orders,
                    created_orders=created_orders,
                    save=False,
                )
                self._snapshots.append(snapshot)
                self._configuration_service.add_value(
                    LAST_SNAPSHOT_DATETIME, current_datetime
                )

    def initialize(
        self,
        algorithm: Algorithm,
        trade_order_evaluator: TradeOrderEvaluator,
    ):
        """
        Initializes the event loop service by calculating the schedule for
        running strategies and tasks based on their defined intervals and time
        units (seconds, minutes, hours).

        The next run times for each strategy are initialized to the current
        time in UTC.

        Args:
            algorithm (Algorithm): The trading algorithm to be run by
                the event loop. This should contain the strategies and
                tasks to be executed.
            trade_order_evaluator (TradeOrderEvaluator): The evaluator
                responsible for checking and updating pending orders,
                stop losses, and take profits.

        Returns:
            None
        """
        self._algorithm = algorithm
        self.strategies = algorithm.strategies
        self.tasks = algorithm.tasks

        if len(self.strategies) == 0:
            raise OperationalException(
                "No strategies are defined in the algorithm. "
                "Please add at least one strategy to the algorithm."
            )

        self._trade_order_evaluator = trade_order_evaluator
        start_date = self._configuration_service.config[INDEX_DATETIME]

        self.next_run_times = {
            strategy.strategy_id: {
                "next_run": start_date,
                "data_sources": strategy.data_sources
            }
            for strategy in self.strategies
        }

        # Collect all data sources and initialize history
        for strategy in self.strategies:

            if strategy.data_sources is not None:
                self.data_sources = self.data_sources.union(
                    set(strategy.data_sources)
                )

            self.history[strategy.strategy_id] = {"runs": []}
            self._strategies_lookup[strategy.strategy_profile.strategy_id] \
                = strategy

        if self._trade_order_evaluator is None:
            raise OperationalException(
                "No trade order evaluator is set for the event loop service."
            )

    def cleanup(self):
        """
        Cleans up the event loop service by saving all snapshots
        taken during the event loop run. The snapshots are saved at the
        end of the event to prevent too many database writes during the
        event loop execution. Saving snapshots in bulk at the end improves
        performance and reduces the number of database transactions.

        Returns:
            None
        """
        self._portfolio_snapshot_service.save_all(self._snapshots)
        # Reset per-run pipeline state so a subsequent run re-runs
        # live envelope validation and starts with a fresh universe
        # cache.
        self._pipeline_universe_cache.clear()
        self._pipelines_live_validated = False

    def start(
        self,
        number_of_iterations=None,
        schedule: pl.DataFrame = None,
        show_progress: bool = False
    ):
        """
        Runs the event loop for the trading algorithm. You can run the
        event loop with different specifications:

        - If `number_of_iterations` is provided, the event loop will run
            for that many iterations.
        - If `schedule` is provided, the event loop will run according to
            the schedule, iterating through each row and using the "date"
            column to determine the current date for that iteration.

        Args:
            number_of_iterations: Optional; the number of iterations to run.
                If None, runs indefinitely.
            schedule: Dict Optional; a schedule to run the event loop with.
            show_progress: Optional; whether to show progress bar for the
                event loop. Defaults to False.
        Returns:
            None
        """

        if schedule is not None:
            sorted_times = sorted(schedule.keys())

            if show_progress:
                for current_time in tqdm(
                    sorted_times,
                    total=len(sorted_times),
                    colour="GREEN",
                    desc="Running event backtest"
                ):
                    self._configuration_service.add_value(
                        INDEX_DATETIME, current_time
                    )
                    strategy_ids = schedule[current_time]["strategy_ids"]
                    strategies = self._get_strategies(strategy_ids)
                    self._run_iteration(
                        strategies=strategies
                    )

            else:
                for current_time in sorted_times:
                    self._configuration_service.add_value(
                        INDEX_DATETIME, current_time
                    )
                    strategy_ids = schedule[current_time]["strategy_ids"]
                    # task_ids = schedule[current_time]["task_ids"]
                    strategies = self._get_strategies(strategy_ids)
                    self._run_iteration(
                        strategies=strategies
                    )
        else:
            if number_of_iterations is None:
                try:
                    config = self._configuration_service.config
                    current_time = config[INDEX_DATETIME]
                    strategies = self._get_due_strategies(current_time)
                    self._run_iteration(
                        strategies=strategies, tasks=self.tasks
                    )
                    current_time = datetime.now(timezone.utc)
                    self._configuration_service.add_value(
                        INDEX_DATETIME, current_time
                    )
                    sleep(1)
                except KeyboardInterrupt:
                    exit(0)
            else:

                if show_progress:
                    for _ in tqdm(
                        range(number_of_iterations),
                        colour="GREEN"
                    ):
                        try:
                            config = self._configuration_service.config
                            current_time = config[INDEX_DATETIME]
                            strategies = self._get_due_strategies(current_time)
                            self._run_iteration(
                                strategies=strategies, tasks=self.tasks
                            )
                            current_time = datetime.now(timezone.utc)
                            self._configuration_service.add_value(
                                INDEX_DATETIME, current_time
                            )
                            sleep(1)
                        except KeyboardInterrupt:
                            exit(0)

                for _ in range(number_of_iterations):
                    try:
                        config = self._configuration_service.config
                        current_time = config[INDEX_DATETIME]
                        strategies = self._get_due_strategies(current_time)
                        self._run_iteration(
                            strategies=strategies, tasks=self.tasks
                        )
                        current_time = datetime.now(timezone.utc)
                        self._configuration_service.add_value(
                            INDEX_DATETIME, current_time
                        )
                        sleep(1)
                    except KeyboardInterrupt:
                        exit(0)

        self.cleanup()

    # ------------------------------------------------------------------ #
    # Pipeline live-mode helpers (#503 phase 3b/3c/3d)
    # ------------------------------------------------------------------ #
    # Envelope: v1 of live pipelines supports daily timeframes only and
    # caps universes at 50 symbols per pipeline. Any sub-daily timeframe
    # on a strategy that declares pipelines, or a strategy whose total
    # OHLCV symbol set exceeds the cap, raises at first iteration when
    # running outside backtest mode. See #503.
    _LIVE_MAX_PIPELINE_SYMBOLS: int = 50
    _LIVE_MIN_TIMEFRAME_MINUTES: int = 24 * 60  # daily

    def _validate_live_envelope(
        self, strategies: List[TradingStrategy]
    ) -> None:
        """Validate the v1 live-pipeline envelope (max 50 symbols /
        daily-or-coarser timeframes). Called once per run when env is
        not BACKTEST. Raises :class:`OperationalException` on
        violation."""
        for strategy in strategies or []:
            pipelines = getattr(strategy, "pipelines", None)
            if not pipelines:
                continue

            ohlcv_sources = [
                ds for ds in (strategy.data_sources or [])
                if DataType.OHLCV.equals(ds.data_type)
            ]

            sub_daily = [
                ds for ds in ohlcv_sources
                if ds.time_frame is not None
                and ds.time_frame.amount_of_minutes
                < self._LIVE_MIN_TIMEFRAME_MINUTES
            ]
            if sub_daily:
                desc = ", ".join(
                    f"{ds.symbol}@{ds.time_frame.value}"
                    for ds in sub_daily
                )
                raise OperationalException(
                    f"Strategy '{strategy.strategy_id}' declares "
                    f"pipelines but uses sub-daily OHLCV timeframes "
                    f"in live mode: {desc}. v1 of the live pipeline "
                    f"engine supports daily timeframes only — see "
                    f"#503. Use a daily timeframe or run the strategy "
                    f"in backtest mode."
                )

            unique_symbols = {ds.symbol for ds in ohlcv_sources}
            unique_symbols.discard(None)
            if len(unique_symbols) > self._LIVE_MAX_PIPELINE_SYMBOLS:
                raise OperationalException(
                    f"Strategy '{strategy.strategy_id}' declares "
                    f"pipelines over {len(unique_symbols)} symbols, "
                    f"which exceeds the v1 live cap of "
                    f"{self._LIVE_MAX_PIPELINE_SYMBOLS}. Reduce the "
                    f"universe or run the strategy in backtest mode "
                    f"(see #503)."
                )

    def _maybe_validate_live_envelope(
        self, strategies: List[TradingStrategy], environment: str
    ) -> None:
        """One-shot envelope validation; no-op for BACKTEST mode."""
        if self._pipelines_live_validated:
            return
        if Environment.BACKTEST.equals(environment):
            self._pipelines_live_validated = True
            return
        self._validate_live_envelope(strategies)
        self._pipelines_live_validated = True

    def _filter_symbols_for_universe_cache(
        self,
        strategy_id: str,
        pipeline_cls: Type,
        symbol_to_identifier: Dict[str, str],
        as_of: datetime,
    ) -> Optional[Dict[str, str]]:
        """If ``pipeline_cls`` declares ``refresh_universe_every`` and
        we have a cached surviving-symbol set still inside the cadence,
        return a restricted ``symbol_to_identifier`` mapping. Returning
        ``None`` means "no cache hit — run a full universe evaluation".
        """
        cadence: Optional[timedelta] = getattr(
            pipeline_cls, "refresh_universe_every", None
        )
        if cadence is None or cadence <= timedelta(0):
            return None

        cache_key = (strategy_id, pipeline_cls)
        cached = self._pipeline_universe_cache.get(cache_key)
        if cached is None:
            return None

        last_refresh, symbols = cached
        # Normalise tz so naive backtest datetimes and aware live
        # datetimes compare cleanly.
        if last_refresh.tzinfo is None and as_of.tzinfo is not None:
            cmp_as_of = as_of.replace(tzinfo=None)
        elif last_refresh.tzinfo is not None and as_of.tzinfo is None:
            cmp_as_of = as_of.replace(tzinfo=last_refresh.tzinfo)
        else:
            cmp_as_of = as_of
        if cmp_as_of - last_refresh >= cadence:
            return None  # cadence elapsed → refresh

        # Cache hit: restrict the symbol set, skipping the universe
        # filter entirely on this iteration.
        return {
            sym: ident
            for sym, ident in symbol_to_identifier.items()
            if sym in symbols
        }

    def _run_pipelines(
        self,
        strategy: TradingStrategy,
        data: Dict,
        data_object: Dict,
        as_of: datetime,
    ) -> None:
        """Compute cross-sectional pipelines attached to ``strategy``
        and inject their outputs into ``data`` keyed by pipeline
        class name.

        Strategies without ``pipelines`` skip this entirely (zero cost).

        Live-mode hardening (#503):

        * The v1 envelope (max 50 symbols, daily-or-coarser timeframes)
          is validated once per run.
        * Pipelines that declare ``refresh_universe_every`` reuse the
          last surviving symbol set within the cadence — saving the
          cost of evaluating the universe filter every bar.
        * In non-backtest environments, a single failing pipeline is
          logged and skipped (the iteration continues with an empty
          output) instead of killing the whole event loop. Backtests
          keep raising so failures stay deterministic.
        """
        pipelines = getattr(strategy, "pipelines", None)
        if not pipelines:
            return

        config = self._configuration_service.get_config()
        environment = config[ENVIRONMENT]
        is_backtest = Environment.BACKTEST.equals(environment)

        # Map symbol -> data-source identifier from the strategy's
        # OHLCV data sources. If a symbol appears on multiple data
        # sources (e.g. multiple timeframes) the first OHLCV match wins.
        symbol_to_identifier: Dict[str, str] = {}
        for ds in strategy.data_sources or []:
            if not DataType.OHLCV.equals(ds.data_type):
                continue
            if ds.symbol is None or ds.symbol in symbol_to_identifier:
                continue
            symbol_to_identifier[ds.symbol] = ds.get_identifier()

        if not symbol_to_identifier:
            logger.warning(
                "Strategy %s declares pipelines but has no OHLCV data "
                "sources to feed them; pipelines will be skipped.",
                strategy.strategy_id,
            )
            return

        for pipeline_cls in pipelines:
            # 3c: universe-refresh cache. If the pipeline declares a
            # refresh cadence and we're inside it, restrict the panel
            # input to the cached symbols.
            cached_mapping = self._filter_symbols_for_universe_cache(
                strategy_id=strategy.strategy_id,
                pipeline_cls=pipeline_cls,
                symbol_to_identifier=symbol_to_identifier,
                as_of=as_of,
            )
            mapping = (
                cached_mapping
                if cached_mapping is not None
                else symbol_to_identifier
            )

            try:
                output = self._pipeline_engine.evaluate(
                    pipeline_cls=pipeline_cls,
                    data_object=data_object,
                    symbol_to_identifier=mapping,
                    as_of=as_of,
                )
            except Exception:
                # 3d: live-mode resilience. In live trading a single
                # pipeline failure must not kill the iteration —
                # surface an empty frame and log so the rest of the
                # strategies can still run. Backtests re-raise so
                # failures stay deterministic.
                logger.exception(
                    "Pipeline %s failed during evaluation at %s",
                    pipeline_cls.__name__,
                    as_of,
                )
                if is_backtest:
                    raise
                output = self._pipeline_engine._empty_output(
                    pipeline_cls
                )

            # 3c: refresh the universe cache when we just ran a full
            # evaluation (cached_mapping was None) and the pipeline
            # declares a cadence.
            cadence = getattr(
                pipeline_cls, "refresh_universe_every", None
            )
            if (
                cadence is not None
                and cadence > timedelta(0)
                and cached_mapping is None
                and "symbol" in output.columns
            ):
                surviving = frozenset(output["symbol"].to_list())
                self._pipeline_universe_cache[
                    (strategy.strategy_id, pipeline_cls)
                ] = (as_of, surviving)

            data[pipeline_cls.__name__] = output

    def _run_iteration(
        self,
        strategies: List[TradingStrategy] = None,
        tasks: List = None
    ):
        """
        Runs a single iteration of the event loop. This method collects all
        due strategies, fetches their data configurations, and runs the
        strategies with the collected data. It also checks for pending orders,
        stop loss orders, and take profit orders, and updates their status if
        needed. Finally, it runs all tasks and strategies, and takes a snapshot
        of the portfolios if needed.

        Args:
            strategies: Optional; a list of strategies to
                run in this iteration. If None, uses the strategies
                defined in the event loop service.
            tasks: Optional; a list of tasks to run in this iteration.
                If None, uses the tasks defined in the event loop service.

        Returns:
            None
        """
        config = self._configuration_service.get_config()
        environment = config[ENVIRONMENT]
        current_datetime = config[INDEX_DATETIME]

        # Validate the live-pipeline envelope (max 50 symbols /
        # daily-or-coarser timeframes) once per run. No-op for
        # backtests. See #503 phase 3b.
        self._maybe_validate_live_envelope(strategies, environment)

        # Step 1: Collect all data for the strategies and for the
        # pending orders
        open_orders = self._order_service.get_all(
            {
                "status": OrderStatus.OPEN,
            }
        )
        open_trades = self._trade_service.get_all(
            {
                "status": TradeStatus.OPEN,
            }
        )
        data_sources = []

        for strategy in strategies:

            if strategy.data_sources is None:
                continue

            data_sources.extend(strategy.data_sources)

        data_sources = self._get_data_sources_for_iteration(
            strategy_data_sources=data_sources,
        )
        data_object = {}
        orders_trades_update_ohlcv_data = \
            self._get_pending_orders_and_trades_data_for_iteration(
                pending_order=open_orders,
                open_trades=open_trades,
                date=current_datetime,
            )

        if Environment.BACKTEST.equals(environment):

            for data_source in data_sources:
                # For backtesting, we use the start date and end date
                # from the data source to fetch the data
                data_object[data_source.get_identifier()] = \
                    self._data_provider_service.get_backtest_data(
                        data_source=data_source,
                        backtest_index_date=current_datetime,
                        start_date=data_source.start_date,
                        end_date=data_source.end_date,
                    )
        else:
            for data_source in data_sources:
                data_object[data_source.get_identifier()] = \
                    self._data_provider_service.get_data(
                        data_source=data_source,
                        date=current_datetime,
                        start_date=data_source.start_date,
                        end_date=data_source.end_date,
                    )

        # Step 3: Check pending orders, stop losses, take profits
        self._trade_order_evaluator.evaluate(
            open_trades=open_trades,
            open_orders=open_orders,
            ohlcv_data=orders_trades_update_ohlcv_data
        )

        # Step 4: Run all tasks
        for task in self.tasks:
            task.run(data_object)

        # Step 5: Run all strategies
        if not strategies:
            return

        for task in self.tasks:
            logger.info(f"Running task {task.__class__.__name__}")

        for strategy in strategies:

            if strategy.data_sources is not None:
                data = {
                    data_source.get_identifier(): data_object[
                        data_source.get_identifier()]
                    for data_source in strategy.data_sources
                }
            else:
                data = {}

            # Step 5b: Run any cross-sectional pipelines attached to
            # the strategy (Phase 1 of the Pipeline API, see
            # docs/design/pipeline-api.md). Strategies without
            # ``pipelines`` skip this entirely.
            self._run_pipelines(
                strategy=strategy,
                data=data,
                data_object=data_object,
                as_of=current_datetime,
            )

            for on_strategy_run_hook in \
                    self._algorithm.on_strategy_run_hooks:
                on_strategy_run_hook.execute(
                    strategy=strategy,
                    context=self.context,
                    data=data
                )

            logger.info(f"Running strategy {strategy.strategy_id}")
            strategy.run_strategy(context=self.context, data=data)

        # Step 7: Snapshot the portfolios if needed and update history
        created_orders = self._order_service.get_all(
            {
                "status": OrderStatus.CREATED,
            }
        )
        open_orders = self._order_service.get_all(
            {
                "status": OrderStatus.OPEN,
            }
        )
        self._snapshot(
            current_datetime=current_datetime,
            open_orders=open_orders,
            created_orders=created_orders
        )
        self._update_history(
            current_datetime=current_datetime,
            strategies=strategies,
            hooks=[]
        )

    def _update_history(self, current_datetime, strategies, hooks):
        """
        Updates the history of the event loop with the current datetime.
        This method is called at the end of each iteration to keep track of
        the iterations.

        Args:
            current_datetime: The current datetime in UTC.

        Returns:
            None
        """

        for strategy in strategies:
            runs = self.history.get(strategy.strategy_id, {}).get("runs", [])
            runs.append(current_datetime)
            self.history[strategy.strategy_id] = {
                "runs": runs,
            }

    @property
    def total_number_of_runs(self):
        """
        Returns the total number of runs for all strategies in the event loop.

        Returns:
            int: The total number of runs.
        """
        return sum(
            len(self.history[strategy_id]["runs"])
            for strategy_id in self.history
        )
