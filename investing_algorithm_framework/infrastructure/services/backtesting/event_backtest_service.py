import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List

from investing_algorithm_framework.domain import BacktestDateRange, \
    BacktestRun, TimeUnit, generate_backtest_summary_metrics, Backtest
from investing_algorithm_framework.services import DataProviderService, \
    create_backtest_metrics


logger = logging.getLogger(__name__)


class EventBacktestService:
    """
    Service that handles event-driven backtesting.

    This service encapsulates the logic for running event-driven backtests,
    where the strategy's `on_run` method is called at each scheduled time
    step. This is different from vectorized backtesting where buy/sell
    signals are generated in a vectorized manner.

    The event-driven backtest simulates the trading bot running in real-time,
    executing strategies at their scheduled intervals and processing orders,
    trades, stop losses, and take profits at each iteration.
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
        """
        Initialize the EventBacktestService.

        Args:
            data_provider_service: Service for fetching market data.
            order_service: Service for managing orders.
            portfolio_service: Service for managing portfolios.
            portfolio_snapshot_service: Service for creating
                portfolio snapshots.
            position_repository: Repository for positions.
            trade_service: Service for managing trades.
            configuration_service: Service for configuration management.
            portfolio_configuration_service: Service for
                portfolio configuration.
        """
        self._data_provider_service = data_provider_service
        self._order_service = order_service
        self._portfolio_service = portfolio_service
        self._portfolio_snapshot_service = portfolio_snapshot_service
        self._position_repository = position_repository
        self._trade_service = trade_service
        self._configuration_service = configuration_service
        self._portfolio_configuration_service = portfolio_configuration_service

    def run(
        self,
        algorithm,
        backtest_date_range: BacktestDateRange,
        risk_free_rate: float,
        event_loop_service,
        trade_order_evaluator,
        show_progress: bool = True,
    ) -> BacktestRun:
        """
        Run an event-driven backtest for an algorithm.

        This method executes the algorithm's strategies according to their
        scheduled intervals, simulating real-time trading behavior.

        Args:
            algorithm: The algorithm containing strategies and tasks to run.
            backtest_date_range: The date range for the backtest.
            risk_free_rate: The risk-free rate for calculating metrics.
            event_loop_service: The event loop service instance
                (pre-configured).
            trade_order_evaluator: The trade order evaluator for handling
                pending orders, stop losses, and take profits.
            show_progress: Whether to show progress bars.

        Returns:
            BacktestRun: The backtest run containing results and metrics.
        """
        # Generate schedule
        schedule = self.generate_schedule(
            algorithm.strategies,
            algorithm.tasks,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Initialize and run the event loop
        event_loop_service.initialize(
            algorithm=algorithm,
            trade_order_evaluator=trade_order_evaluator
        )
        event_loop_service.start(
            schedule=schedule, show_progress=show_progress
        )

        # Create backtest run from results
        return self._create_backtest_run(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            number_of_runs=event_loop_service.total_number_of_runs,
            risk_free_rate=risk_free_rate,
        )

    def generate_schedule(
        self,
        strategies,
        tasks,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[datetime, Dict[str, List[str]]]:
        """
        Generates a dict-based schedule: datetime => {strategy_ids, task_ids}

        This schedule determines when each strategy should be executed during
        the backtest based on their defined time units and intervals.

        Args:
            strategies: List of strategies to schedule.
            tasks: List of tasks to schedule.
            start_date: Start date of the backtest.
            end_date: End date of the backtest.

        Returns:
            Dict mapping datetime to strategy_ids and task_ids to run.
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

    def _create_backtest_run(
        self,
        algorithm,
        backtest_date_range: BacktestDateRange,
        number_of_runs: int,
        risk_free_rate: float,
    ) -> BacktestRun:
        """
        Create a BacktestRun from the current state after event loop execution.

        Args:
            algorithm: The algorithm that was backtested.
            backtest_date_range: The date range of the backtest.
            number_of_runs: Total number of strategy executions.
            risk_free_rate: Risk-free rate for metrics calculation.

        Returns:
            BacktestRun: The completed backtest run with metrics.
        """
        # Get the portfolio
        portfolio = self._portfolio_service.get_all()[0]

        # Get initial unallocated amount
        initial_unallocated = self._get_initial_unallocated()

        # Create the backtest run
        run = BacktestRun(
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            initial_unallocated=initial_unallocated,
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

        # Calculate and add metrics
        backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        run.backtest_metrics = backtest_metrics

        return run

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
        backtest_date_range: BacktestDateRange,
        number_of_runs: int,
        risk_free_rate: float,
    ) -> Backtest:
        """
        Create a Backtest object from the current state.

        This method creates a full Backtest object containing the backtest
        run, metrics, and summary.

        Args:
            algorithm: The algorithm that was backtested.
            backtest_date_range: The date range of the backtest.
            number_of_runs: Total number of strategy executions.
            risk_free_rate: Risk-free rate for metrics calculation.

        Returns:
            Backtest: The completed backtest with run and summary.
        """
        run = self._create_backtest_run(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            number_of_runs=number_of_runs,
            risk_free_rate=risk_free_rate,
        )

        algorithm_id = (
            algorithm.algorithm_id
            if hasattr(algorithm, 'algorithm_id')
            else algorithm.id
        )

        return Backtest(
            algorithm_id=algorithm_id,
            backtest_runs=[run],
            backtest_summary=generate_backtest_summary_metrics(
                [run.backtest_metrics]
            ),
            risk_free_rate=risk_free_rate,
        )
