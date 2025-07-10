import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import polars as pl
from tqdm import tqdm

from investing_algorithm_framework.domain import BacktestResult, \
    BACKTESTING_INDEX_DATETIME, TimeUnit, TradingDataType, \
    OperationalException, MarketDataSource, Observable, Event, \
    BacktestDateRange, DATETIME_FORMAT_BACKTESTING, Backtest
from investing_algorithm_framework.services.market_data_source_service import \
    MarketDataSourceService
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
        market_data_source_service: MarketDataSourceService,
        order_service,
        portfolio_service,
        portfolio_snapshot_service,
        position_repository,
        trade_service,
        performance_service,
        configuration_service,
        portfolio_configuration_service,
        strategy_orchestrator_service
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
        self._market_data_source_service: MarketDataSourceService \
            = market_data_source_service
        self._configuration_service = configuration_service
        self._portfolio_configuration_service = portfolio_configuration_service
        self._strategy_orchestrator_service = strategy_orchestrator_service

    def run_backtest(
        self,
        algorithm,
        context,
        strategy_orchestrator_service,
        backtest_date_range: BacktestDateRange,
        risk_free_rate,
        initial_amount=None,
        strategy_directory_path=None
    ) -> Backtest:
        """
        Run a backtest for the given algorithm. This function will run
        a backtest for the given algorithm and return a backtest report.

        A schedule is generated for the given algorithm and the strategies
        are run for each date in the schedule.

        Also, all backtest data is downloaded (if not already downloaded) and
        the backtest is run for each date in the schedule.

        Args:
            algorithm: The algorithm to run the backtest for
            backtest_date_range: The backtest date range
            initial_amount: The initial amount of the backtest portfolio
            strategy_orchestrator_service: The strategy orchestrator service
            context (Context): The context of the object of the application
            risk_free_rate (float): The risk-free rate to use in the metrics
                calculations
            strategy_directory_path (optional, str): The path to the
                strategy directory. If not provided, the strategies will be
                loaded from the algorithm object.

        Returns:
            Backtest: The backtest
        """
        logging.info(
            f"Running backtest for algorithm with name {algorithm.name}"
        )

        # Create backtest portfolio
        portfolio_configurations = \
            self._portfolio_configuration_service.get_all()

        for portfolio_configuration in portfolio_configurations:

            if self._portfolio_service.exists(
                {"identifier": portfolio_configuration.identifier}
            ):
                # Delete existing portfolio
                portfolio = self._portfolio_service.find(
                    {"identifier": portfolio_configuration.identifier}
                )
                self._portfolio_service.delete(portfolio.id)

            # Check if the portfolio configuration has an initial balance
            self._portfolio_service.create_portfolio_from_configuration(
                portfolio_configuration,
                initial_amount=initial_amount,
                created_at=backtest_date_range.start_date,
            )

        strategy_profiles = []
        portfolios = self._portfolio_service.get_all()
        initial_unallocated = 0

        for portfolio in portfolios:
            initial_unallocated += portfolio.unallocated

        for strategy in algorithm.strategies:
            strategy_profiles.append(strategy.strategy_profile)

        schedule = self.generate_schedule(
            strategies=algorithm.strategies,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date
        )

        logger.info(f"Prepared backtests for {len(schedule)} strategies")

        for row in tqdm(
            schedule.to_dicts(),
            total=len(schedule),
            desc=f"Running backtest for algorithm with name {algorithm.name}",
            colour="GREEN"
        ):
            strategy_profile = self.get_strategy_from_strategy_profiles(
                strategy_profiles, row['id']
            )
            index_date = row["run_time"]
            self._configuration_service.add_value(
                BACKTESTING_INDEX_DATETIME, index_date
            )
            config = self._configuration_service.get_config()
            strategy = algorithm.get_strategy(strategy_profile.strategy_id)
            strategy_orchestrator_service.run_backtest_strategy(
                context=context, strategy=strategy, config=config
            )
            self.notify_observers(Event.STRATEGY_RUN, {
                "created_at": index_date,
            })

        report = self.create_backtest(
            algorithm,
            number_of_runs=len(schedule),
            backtest_date_range=backtest_date_range,
            initial_unallocated=initial_unallocated,
            risk_free_rate=risk_free_rate,
            strategy_directory_path=strategy_directory_path
        )

        # Cleanup backtest portfolio
        portfolio_configurations = \
            self._portfolio_configuration_service.get_all()

        for portfolio_configuration in portfolio_configurations:
            portfolio = self._portfolio_service.find(
                {"identifier": portfolio_configuration.identifier}
            )
            self._portfolio_service.delete(portfolio.id)

        return report

    def run_backtest_for_profile(
        self, context, algorithm, strategy, index_date
    ):
        self._configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME, index_date
        )
        algorithm.config[BACKTESTING_INDEX_DATETIME] = index_date
        market_data = {}

        if strategy.strategy_profile.market_data_sources is not None:

            for data_id in strategy.strategy_profile.market_data_sources:

                if isinstance(data_id, MarketDataSource):
                    market_data[data_id.get_identifier()] = \
                        self._market_data_source_service.get_data(
                            data_id.get_identifier()
                        )
                else:
                    market_data[data_id] = \
                        self._market_data_source_service.get_data(data_id)

        strategy.run_strategy(context=context, market_data=market_data)

    def run_backtest_v2(self, strategy, context):
        config = self._configuration_service.get_config()
        self._strategy_orchestrator_service.run_backtest_strategy(
            context=context, strategy=strategy, config=config
        )

    def generate_schedule(
        self, strategies, start_date, end_date
    ) -> pl.DataFrame:
        """
        Generate a schedule using Polars.

        Args:
            strategies: The strategies to generate the schedule for
            start_date: The start datetime
            end_date: The end datetime

        Returns:
            pl.DataFrame: The schedule
        """
        rows = []

        for strategy in strategies:
            strategy_id = strategy.strategy_profile.strategy_id
            time_unit = strategy.strategy_profile.time_unit
            interval = strategy.strategy_profile.interval
            current_time = start_date

            delta = None
            if TimeUnit.SECOND.equals(time_unit):
                delta = timedelta(seconds=interval)
            elif TimeUnit.MINUTE.equals(time_unit):
                delta = timedelta(minutes=interval)
            elif TimeUnit.HOUR.equals(time_unit):
                delta = timedelta(hours=interval)
            elif TimeUnit.DAY.equals(time_unit):
                delta = timedelta(days=interval)
            else:
                raise ValueError(f"Unsupported time unit: {time_unit}")

            while current_time <= end_date:
                rows.append((strategy_id, current_time))
                current_time += delta

        if not rows:
            raise OperationalException(
                "Could not generate schedule for backtest. "
                "Do you have a strategy registered?"
            )

        df = pl.DataFrame(rows, schema=["id", "run_time"], orient="row")

        return df.sort("run_time")

    def get_strategy_from_strategy_profiles(self, strategy_profiles, id):

        for strategy_profile in strategy_profiles:

            if strategy_profile.strategy_id == id:
                return strategy_profile

        raise ValueError(f"Strategy profile with id {id} not found.")

    def create_backtest(
        self,
        algorithm,
        number_of_runs,
        backtest_date_range: BacktestDateRange,
        risk_free_rate,
        initial_unallocated=0,
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
            initial_unallocated: The initial unallocated amount
            risk_free_rate: The risk-free rate to use in the calculations
            strategy_directory_path (optional, str): The path to the
                strategy directory

        Returns:
            Backtest: The backtest containing the results and metrics.
        """

        for portfolio in self._portfolio_service.get_all():
            ids = [strategy.strategy_id for strategy in algorithm.strategies]

            # Check if strategy_id is None
            if None in ids:
                # Remove None from ids
                ids = [x for x in ids if x is not None]

            positions = self._position_repository.get_all({
                "portfolio": portfolio.id
            })
            tickers = {}

            for position in positions:

                if position.symbol != portfolio.trading_symbol:
                    ticker_symbol = \
                        f"{position.symbol}/{portfolio.trading_symbol}"

                    if not self._market_data_source_service\
                            .has_ticker_market_data_source(
                                symbol=ticker_symbol, market=portfolio.market
                            ):
                        raise OperationalException(
                            f"Ticker market data source for "
                            f"symbol {ticker_symbol} and market "
                            f"{portfolio.market} not found, please make "
                            f"sure you register a ticker market data "
                            f"source for this symbol and market in "
                            f"backtest mode. Otherwise, the backtest "
                            f"report cannot be generated."
                        )
                    symbol = f"{position.symbol}/{portfolio.trading_symbol}"
                    tickers[ticker_symbol] = \
                        self._market_data_source_service.get_ticker(
                            symbol=symbol, market=portfolio.market
                        )

            # Create the last snapshot of the portfolio
            self._portfolio_snapshot_service.create_snapshot(
                portfolio=portfolio,
                created_at=backtest_date_range.end_date
            )

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
        backtest_metrics = create_backtest_metrics(
            backtest_result, risk_free_rate=risk_free_rate
        )
        return Backtest(
            backtest_results=backtest_result,
            backtest_metrics=backtest_metrics,
            strategy_related_paths=strategy_related_paths,
            data_file_paths=self._market_data_source_service.get_data_files(),
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
