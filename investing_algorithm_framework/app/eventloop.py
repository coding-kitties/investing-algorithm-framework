from datetime import datetime, timedelta, timezone
from time import sleep
from typing import List, Set, Dict
from logging import getLogger

import polars as pl

from investing_algorithm_framework.domain import Environment, ENVIRONMENT, \
    OrderStatus, DataSource, DataType, tqdm, \
    TradeStatus, SNAPSHOT_INTERVAL, SnapshotInterval, OperationalException, \
    LAST_SNAPSHOT_DATETIME, INDEX_DATETIME
from investing_algorithm_framework.services import TradeOrderEvaluator

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
