from typing import List
from datetime import  datetime, timedelta, timezone
from investing_algorithm_framework.domain import TimeUnit, ENVIRONMENT, \
    Environment, BACKTESTING_INDEX_DATETIME
from .strategy import TradingStrategy


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
        - Check all pending orders and update their status if needed
        - Check all stop loss orders and update their status if needed
        - Check all take profit orders and update their status if needed
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
        order_service,
        portfolio_service,
        configuration_service,
        data_provider_service=None
    ):
        """
        Initializes the event loop service with the provided algorithm.

        Args:
            order_service: The service responsible for managing orders.
            portfolio_service: The service responsible for managing portfolios.
            configuration_service: The service responsible for configuration.
        """
        self.tasks = []
        self._algorithm = None
        self._strategies = []
        self._order_service = order_service
        self._portfolio_service = portfolio_service
        self._configuration_service = configuration_service
        self._data_provider_service = data_provider_service
        self._data_configurations = []
        self.next_run_times = {}

    def _get_due_strategies(self):
        """
        Checks which strategies are due to run based on their defined intervals
        Returns:

        """
        environment = self._configuration_service.config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            now = self._configuration_service\
                .config[BACKTESTING_INDEX_DATETIME]
        else:
            now = datetime.now(timezone.utc)

        due = []

        for strategy in self._strategies:
            interval = timedelta(
                **{strategy.time_unit.value.lower(): strategy.interval}
            )

            if now >= self.next_run_times[strategy]:
                due.append(strategy)
                self.next_run_times[strategy] = now + interval

        return due

    def initialize(self, algorithm):
        """
        Initializes the event loop service by calculating the schedule for
        running strategies and tasks based on their defined intervals and time
        units (seconds, minutes, hours).

        The next run times for each strategy are initialized to the current
        time in UTC.

        Args:
            algorithm: The trading algorithm to be managed by this service.

        Returns:
            None
        """
        
        self._algorithm = algorithm
        self._strategies = algorithm.strategies
        self.next_run_times = {
            strategy.identifier: {
                "next_run": datetime.now(timezone.utc)
                "data_configurations": strategy.data_configurations
            }
            for strategy in self._strategies
        }

        # Collect all data configurations
        for strategy in self._strategies:
            self._data_configurations.append(
                strategy.data_configurations
            )

    def start(self, number_of_iterations=None):
        """
        Runs the event loop for the trading algorithm.

        Args:
            number_of_iterations: Optional; the number of iterations to run.
                If None, runs indefinitely.
        """
        pass

    def _run_iteration_backtest(self):
        """
        Runs a single iteration of the event loop in backtesting mode.
        This method collects all due strategies, fetches their data
        configurations, and runs the strategies with the collected data.

        Returns:
            None
        """
        due_strategies = self._get_due_strategies()

        if not due_strategies:
            return

        # Step 1: Collect all data
        data_configurations = []

        for strategy in due_strategies:
            data_configurations.extend(strategy.data_configurations)

        # Make sure we have unique data configurations
        data_configurations = list(set(data_configurations))
        data_object = {}

        for data_config in data_configurations:
            data_object[data_config.identifier] = \
                self._data_provider_service.get_backest_data(
                    symbol=data_config.symbol,
                    data_type=data_config.data_type,
                    date=data_config.date,
                    market=data_config.market,
                    time_frame=data_config.time_frame,
                    start_date=data_config.start_date,
                    end_date=data_config.end_date,
                    window_size=data_config.window_size,
                    pandas=data_config.pandas,
                )

        # Step 2: Update prices of trades

        # Step 3: Check pending orders

        # Step 4: Check stop loss orders

        # Step 5: Check take profit orders

        # Step 6: Run all tasks

        # Step 7: Run all strategies

    def _run_iteration(self):
        """
        Runs a single iteration of the event loop. This method collects all
        due strategies, fetches their data configurations, and runs the
        strategies with the collected data. It also checks for pending orders,
        stop loss orders, and take profit orders, and updates their status if
        needed. Finally, it runs all tasks and strategies, and takes a snapshot
        of the portfolios if needed.

        Returns:
            None
        """
        due_strategies = self._get_due_strategies()

        if not due_strategies:
            return

        # Step 1: Collect all data
        data_configurations = []

        for strategy in due_strategies:
            data_configurations.extend(strategy.data_configurations)

        # Make sure we have unique data configurations
        data_configurations = list(set(data_configurations))
        data_object = {}

        for data_config in data_configurations:
            data_object[data_config.identifier] = \
                self._data_provider_service.get_data(
                    symbol=data_config.symbol,
                    data_type=data_config.data_type,
                    date=data_config.date,
                    market=data_config.market,
                    time_frame=data_config.time_frame,
                    start_date=data_config.start_date,
                    end_date=data_config.end_date,
                    window_size=data_config.window_size,
                    pandas=data_config.pandas,
                )

        # Step 2: Update prices of trades

        # Step 3: Check pending orders

        # Step 4: Check stop loss orders

        # Step 5: Check take profit orders

        # Step 6: Run all tasks

        # Step 7: Run all strategies
