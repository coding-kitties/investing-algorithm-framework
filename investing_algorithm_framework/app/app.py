import inspect
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple, Callable, Union

import uvicorn
from fastapi import FastAPI

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.app.task import Task
from investing_algorithm_framework.app.web import create_fastapi_app
from investing_algorithm_framework.domain import DATABASE_NAME, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, OperationalException, StateHandler, \
    BACKTESTING_START_DATE, BACKTESTING_END_DATE, APP_MODE, MarketCredential, \
    AppMode, BacktestDateRange, BacktestWindow, DATABASE_DIRECTORY_NAME, \
    DataSource, Blotter, \
    BACKTESTING_INITIAL_AMOUNT, SNAPSHOT_INTERVAL, generate_algorithm_id, \
    PortfolioConfiguration, SnapshotInterval, DataType, Backtest, DataError, \
    PortfolioProvider, OrderExecutor, ImproperlyConfigured, TimeFrame, \
    DataProvider, INDEX_DATETIME, tqdm, BacktestMonteCarloTest, \
    LAST_SNAPSHOT_DATETIME, BACKTESTING_FLAG, DATA_DIRECTORY, Schedule, \
    Universe, PositionMode, RunReport, PaperTradingMode
from investing_algorithm_framework.domain.backtesting.study import Study
from investing_algorithm_framework.domain.backtesting.backtest_engine import \
    BacktestEngine
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables, CCXTOrderExecutor, CCXTPortfolioProvider, \
    CCXTOHLCVDataProvider, clear_db, teardown_sqlalchemy, \
    PandasOHLCVDataProvider, BacktestService, PaperTradingOrderExecutor, \
    PaperTradingPortfolioProvider
from investing_algorithm_framework.services import OrderBacktestService, \
    BacktestPortfolioService, DefaultTradeOrderEvaluator
from .app_hook import AppHook
from .eventloop import EventLoopService


logger = logging.getLogger("investing_algorithm_framework")
COLOR_RESET = '\033[0m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'


def _build_strategy_universe_map(strategies, universe):
    """Thin wrapper around the domain helper of the same name; kept for
    backwards compatibility with code paths inside ``app.py``."""
    from investing_algorithm_framework.domain.backtesting import (
        build_strategy_universe_map as _domain_build,
    )
    return _domain_build(strategies, [universe] if universe else None)


def _apply_study_to_backtests(
    backtests,
    study,
    strategies,
    backtest_storage_directory,
    anchor_algorithm_id=None,
):
    """Stamp ``study`` (name, description, initial_capital, universe,
    backtest_windows) and ``anchor_algorithm_id`` onto each Backtest
    produced by the event-driven engine, then (when
    ``backtest_storage_directory`` is set) re-save each bundle once
    with ``merge=True`` so the on-disk envelope reflects all of it.

    Takes the ``Study`` object directly (instead of its fields
    unpacked into separate parameters) so future Study fields don't
    require a new parameter here — see the vector engine's
    ``BacktestService.run_vector_backtests``, which stamps its Study
    natively for the same reason.

    No-op (aside from the universe merge check) if ``study`` and
    ``anchor_algorithm_id`` are both ``None``.
    """
    universe_map = (
        _build_strategy_universe_map(strategies, study.universe)
        if study is not None and study.universe is not None
        else {}
    )

    if study is None and anchor_algorithm_id is None:
        return

    for bt in backtests:
        if study is not None:
            _ds = bt.get_study()
            if study.name is not None and _ds and _ds.name != study.name:
                bt.rename_study(_ds.name, study.name)
                _ds = bt.get_study()
            if _ds:
                if study.description is not None:
                    _ds.description = study.description
                if study.initial_capital is not None:
                    _ds.initial_capital = study.initial_capital
                if study.backtest_windows:
                    _ds.backtest_windows = list(study.backtest_windows)
                    for engine in ("vector", "event"):
                        for run in _ds.get_runs(engine):
                            for window in study.backtest_windows:
                                candidate_ranges = [
                                    r for r in (
                                        window.train_range,
                                        window.test_range,
                                    )
                                    if r is not None
                                ]
                                if any(
                                    run.backtest_start_date == r.start_date
                                    and run.backtest_end_date == r.end_date
                                    for r in candidate_ranges
                                ):
                                    run.backtest_window = window
                                    if run.backtest_metrics is not None:
                                        run.backtest_metrics\
                                            .backtest_window = window
                                    break

            matched = universe_map.get(bt.algorithm_id)
            if matched is not None:
                bt.universes = [matched]
                bt.tag_runs_universe(matched.key, overwrite=False)
                bt.regenerate_summaries_by_universe()
            elif study.universe is not None:
                logger.warning(
                    "Backtest %s has no matching universe; skipping "
                    "universe stamping.", bt.algorithm_id,
                )

        if anchor_algorithm_id is not None:
            bt.anchor_algorithm_id = anchor_algorithm_id

    if backtest_storage_directory is None:
        return

    from investing_algorithm_framework.domain.backtesting.bundle import (
        save_bundle, BUNDLE_EXT,
    )
    from investing_algorithm_framework.domain.backtesting.backtest_utils \
        import resolve_backtest_path

    storage_dir = Path(backtest_storage_directory)
    for bt in backtests:
        target = resolve_backtest_path(storage_dir, bt.algorithm_id)
        if target is None:
            target = storage_dir / f"{bt.algorithm_id}{BUNDLE_EXT}"
        try:
            save_bundle(bt, Path(target), merge=True)
        except Exception as exc:  # pragma: no cover - best-effort restamp
            logger.warning(
                "Failed to re-save backtest %s with study fields: %s",
                bt.algorithm_id, exc,
            )


class App:
    """
    Class to represent the app. This class is used to initialize the
    application and run your trading bot.

    Attributes:
        container: The dependency container for the app. This is used
            to store all the services and repositories for the app.
        _web_app: The FastAPI app instance. This is used to run the
            web app.
        _state_handler: The state handler for the app. This is used
            to save and load the state of the app.
        _name: The name of the app. This is used to identify the app
            in logs and other places.
        _started: A boolean value that indicates if the app has been
            started or not.
        _tasks (List[Task]): List of task that need to be run by the
            application.
    """

    def __init__(self, state_handler=None, name=None):
        self._web_app: Optional[FastAPI] = None
        # Set directly by test harnesses to skip starting a real
        # uvicorn server while still exercising the FastAPI app via
        # its own TestClient (mirrors the old Flask ``app.testing``
        # flag, which lived on the recreated Flask instance instead).
        self._web_app_testing: bool = False
        self.container = None
        self._started = False
        self._tasks = []
        self._strategies = []
        self._data_providers: List[Tuple[DataProvider, int]] = []
        self._on_initialize_hooks = []
        self._on_strategy_run_hooks = []
        self._on_after_initialize_hooks = []
        self._trade_order_evaluator = None
        self._state_handler = state_handler
        self._run_history = None
        self._last_run_report = None
        self._name = name
        self._blotter = None
        self._fx_rate_provider = None
        self._base_currency = None

    @property
    def context(self):
        from investing_algorithm_framework.domain.blotter import \
            DefaultBlotter

        ctx = self.container.context()
        ctx._blotter = self._blotter \
            if self._blotter is not None else DefaultBlotter()
        ctx._fx_rate_provider = self._fx_rate_provider
        ctx._base_currency = self._base_currency

        return ctx

    @property
    def resource_directory_path(self):
        """
        Returns the resource directory path from the configuration.
        This directory is used to store resources such as market data,
        database files, and other resources required by the app.
        """
        config = self.config
        resource_directory_path = config.get(RESOURCE_DIRECTORY, None)

        # Check if the resource directory is set
        if resource_directory_path is None:
            logger.info(
                "Resource directory not set, setting" +
                " to current working directory"
            )
            resource_directory_path = os.path.join(os.getcwd(), "resources")
            configuration_service = self.container.configuration_service()
            configuration_service.add_value(
                RESOURCE_DIRECTORY, resource_directory_path
            )

        return resource_directory_path

    @property
    def database_directory_path(self):
        """
        Returns the database directory path from the configuration.
        This directory is used to store database files required by the app.
        """
        config = self.config
        database_directory_path = config.get(DATABASE_DIRECTORY_PATH, None)

        # Check if the database directory is set
        if database_directory_path is None:
            logger.info(
                "Database directory not set, setting" +
                " to current working directory"
            )
            resource_directory_path = self.resource_directory_path
            database_directory_path = os.path.join(
                resource_directory_path, "databases"
            )
            configuration_service = self.container.configuration_service()
            configuration_service.add_value(
                DATABASE_DIRECTORY_PATH, database_directory_path
            )

        return database_directory_path

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def started(self):
        return self._started

    @property
    def config(self):
        """
        Function to get a config instance. This allows users when
        having access to the app instance also to read the
        configs of the app.
        """
        configuration_service = self.container.configuration_service()
        return configuration_service.config

    @config.setter
    def config(self, config: dict):
        """
        Function to set the configuration for the app.
        Args:
            config (dict): A dictionary containing the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    def add_algorithm(self, algorithm: Algorithm) -> None:
        """
        Method to add an algorithm to the app. This method should be called
        before running the application.

        When adding an algorithm, it will automatically register all
        strategies, data sources, and tasks of the algorithm. The
        algorithm itself is not registered.

        Args:
            algorithm (Algorithm): The algorithm to add to the app.
                This should be an instance of Algorithm.

        Returns:
            None
        """
        self.add_strategies(algorithm.strategies)
        self.add_tasks(algorithm.tasks)

    def add_trade_order_evaluator(self, trade_order_evaluator):
        """
        Function to add a trade order evaluator to the app. This is used
        to evaluate trades and orders based on OHLCV data.

        Args:
            trade_order_evaluator: The trade order evaluator to add to the app.
                This should be an instance of TradeOrderEvaluator.

        Returns:
            None
        """
        self._trade_order_evaluator = trade_order_evaluator

    def set_config(self, key: str, value: Any) -> None:
        """
        Function to add a key-value pair to the app's configuration.

        Args:
            key (string): The key to add to the configuration
            value (any): The value to add to the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.add_value(key, value)

    def set_config_with_dict(self, config: dict) -> None:
        """
        Function to set the configuration for the app with a dictionary.
        This is useful for setting multiple configuration values at once.

        Args:
            config (dict): A dictionary containing the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    def initialize_config(self):
        """
        Function to initialize the configuration for the app. This method
        should be called before running the algorithm.

        Returns:
            None
        """
        data = {
            ENVIRONMENT: self.config.get(ENVIRONMENT, Environment.PROD.value),
            DATABASE_DIRECTORY_NAME: "databases",
            LAST_SNAPSHOT_DATETIME: None
        }
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(data)
        config = configuration_service.get_config()

        if INDEX_DATETIME not in config or config[INDEX_DATETIME] is None:
            configuration_service.add_value(
                INDEX_DATETIME, datetime.now(timezone.utc)
            )

        if Environment.TEST.equals(config[ENVIRONMENT]):
            configuration_service.add_value(
                DATABASE_NAME, "test-database.sqlite3"
            )
        elif Environment.PROD.equals(config[ENVIRONMENT]):
            configuration_service.add_value(
                DATABASE_NAME, "prod-database.sqlite3"
            )
        else:
            configuration_service.add_value(
                DATABASE_NAME, "dev-database.sqlite3"
            )

        resource_dir = config[RESOURCE_DIRECTORY]
        database_dir_name = config.get(DATABASE_DIRECTORY_NAME)
        configuration_service.add_value(
            DATABASE_DIRECTORY_PATH,
            os.path.join(resource_dir, database_dir_name)
        )
        config = configuration_service.get_config()

        if SQLALCHEMY_DATABASE_URI not in config \
                or config[SQLALCHEMY_DATABASE_URI] is None:
            path = "sqlite:///" + os.path.join(
                configuration_service.config[DATABASE_DIRECTORY_PATH],
                configuration_service.config[DATABASE_NAME]
            ).replace("\\", "/")
            configuration_service.add_value(SQLALCHEMY_DATABASE_URI, path)

    def initialize_backtest_config(
        self,
        backtest_date_range: BacktestDateRange,
        initial_amount=None,
        snapshot_interval: SnapshotInterval = None
    ):
        """
        Function to initialize the configuration for the app in backtest mode.
        This method should be called before running the algorithm in backtest
        mode. It sets the environment to BACKTEST and initializes the
        configuration accordingly.

        Args:
            backtest_date_range (BacktestDateRange): The date range for the
                backtest. This should be an instance of BacktestDateRange.
            initial_amount (float): The initial amount to start the backtest
                with. This will be the amount of trading currency that the
                backtest portfolio will start with.
            snapshot_interval (SnapshotInterval): The snapshot interval to
                use for the backtest. This is used to determine how often the
                portfolio snapshot should be taken during the backtest.

        Returns:
            None
        """
        logger.info("Initializing backtest configuration")
        data = {
            ENVIRONMENT: Environment.BACKTEST.value,
            BACKTESTING_START_DATE: backtest_date_range.start_date,
            BACKTESTING_END_DATE: backtest_date_range.end_date,
            DATABASE_NAME: "backtest-database.sqlite3",
            DATABASE_DIRECTORY_NAME: "backtest_databases",
            DATABASE_DIRECTORY_PATH: os.path.join(
                self.resource_directory_path,
                "backtest_databases"
            ),
            BACKTESTING_INITIAL_AMOUNT: initial_amount,
            INDEX_DATETIME: backtest_date_range.start_date,
            LAST_SNAPSHOT_DATETIME: None,
            BACKTESTING_FLAG: True
        }
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(data)

        if snapshot_interval is not None:
            configuration_service.add_value(
                SNAPSHOT_INTERVAL,
                SnapshotInterval.from_value(snapshot_interval).value
            )

    def initialize_storage(self, remove_database_if_exists: bool = False):
        """
        Function to initialize the storage for the app. The given
        resource directory will be created if it does not exist.
        The database directory will also be created if it does not
        exist.
        """
        resource_directory_path = self.resource_directory_path

        if not os.path.exists(resource_directory_path):
            os.makedirs(resource_directory_path)
            logger.info(
                f"Resource directory created at {resource_directory_path}"
            )

        database_directory_path = self.database_directory_path

        if not os.path.exists(database_directory_path):
            os.makedirs(database_directory_path)
            logger.info(
                f"Database directory created at {database_directory_path}"
            )

        database_path = os.path.join(
            database_directory_path, self.config[DATABASE_NAME]
        )

        if remove_database_if_exists:

            if os.path.exists(database_path):
                logger.info(
                    f"Removing existing database at {database_path}"
                )

                # Dispose the existing engine to release file locks
                # (required on Windows where locks are mandatory)
                teardown_sqlalchemy()

                import gc
                gc.collect()

                os.remove(database_path)

        # Create the sqlalchemy database uri
        path = "sqlite:///" + database_path.replace("\\", "/")
        self.set_config(SQLALCHEMY_DATABASE_URI, path)

        # Setup sql if needed
        setup_sqlalchemy(self)
        create_all_tables()

        # Create the DATA_DIRECTORY if it does not exist
        data_directory_dir_name = self.config[DATA_DIRECTORY]
        data_directory_path = os.path.join(
            resource_directory_path, data_directory_dir_name
        )
        if not os.path.exists(data_directory_path):
            os.makedirs(data_directory_path)
            logger.info(
                f"Data directory created at {data_directory_path}"
            )

    def initialize_data_sources(
        self,
        data_sources: List[DataSource],
    ):
        """
        Function to initialize the data sources for the app. This method
        should be called before running the algorithm. This method
        initializes all data sources so that they are ready to be used.

        Args:
            data_sources (List[DataSource]): The data sources to initialize.
                This should be a list of DataSource instances.

        Returns:
            None
        """
        if data_sources is None or len(data_sources) == 0:
            logger.info("No data sources were configured")
            return

        data_provider_service = self.container.data_provider_service()
        data_provider_service.reset()

        for data_provider_tuple in self._data_providers:
            data_provider_service.add_data_provider(
                data_provider_tuple[0], priority=data_provider_tuple[1]
            )

        # Add the default data providers
        data_provider_service.add_data_provider(CCXTOHLCVDataProvider())

        # Initialize all data sources
        data_provider_service.index_data_providers(data_sources)
        identifiers = ', '.join(ds.get_identifier() for ds in data_sources)
        logger.info(
            f"Data sources initialized ({len(data_sources)}): {identifiers}"
        )

    def initialize_data_sources_backtest(
        self,
        data_sources: List[DataSource],
        backtest_date_range: BacktestDateRange,
        show_progress: bool = False,
        fill_missing_data: bool = False,
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
            fill_missing_data (bool): If True, missing time series data
                entries will be filled automatically before preparing the
                backtest data.

        Returns:
            None
        """
        logger.info("Initializing data sources for backtest")

        if data_sources is None or len(data_sources) == 0:
            return

        data_provider_service = self.container.data_provider_service()
        data_provider_service.reset()

        for data_provider_tuple in self._data_providers:
            data_provider_service.add_data_provider(
                data_provider_tuple[0], priority=data_provider_tuple[1]
            )

        # Add the default data providers
        data_provider_service.add_data_provider(CCXTOHLCVDataProvider())

        # Initialize all data sources
        data_provider_service.index_backtest_data_providers(
            data_sources, backtest_date_range, show_progress=show_progress
        )

        description = "Preparing backtest data for all data sources"
        data_providers = data_provider_service.data_provider_index.get_all()

        # Prepare the backtest data for each data provider
        if not show_progress:
            for _, data_provider in data_providers:

                data_provider.prepare_backtest_data(
                    backtest_start_date=backtest_date_range.start_date,
                    backtest_end_date=backtest_date_range.end_date,
                    fill_missing_data=fill_missing_data,
                    show_progress=show_progress,
                )
        else:
            for _, data_provider in \
                    tqdm(
                        data_providers, desc=description, colour="green"
                    ):

                data_provider.prepare_backtest_data(
                    backtest_start_date=backtest_date_range.start_date,
                    backtest_end_date=backtest_date_range.end_date,
                    fill_missing_data=fill_missing_data,
                    show_progress=show_progress,
                )

    def initialize_backtest_services(self):
        """
        Function to initialize the backtest services for the app. This method
        should be called before running the algorithm in backtest mode.
        It initializes the backtest services so that they are ready to be used.

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        self.initialize_order_executors()
        self.initialize_portfolio_providers()
        portfolio_conf_service = self.container \
            .portfolio_configuration_service()
        portfolio_snap_service = self.container \
            .portfolio_snapshot_service()
        market_cred_service = self.container.market_credential_service()
        portfolio_provider_lookup = \
            self.container.portfolio_provider_lookup()
        # Override the portfolio service with the backtest portfolio service
        self.container.portfolio_service.override(
            BacktestPortfolioService(
                configuration_service=configuration_service,
                market_credential_service=market_cred_service,
                position_service=self.container.position_service(),
                order_service=self.container.order_service(),
                portfolio_repository=self.container.portfolio_repository(),
                portfolio_configuration_service=portfolio_conf_service,
                portfolio_snapshot_service=portfolio_snap_service,
                portfolio_provider_lookup=portfolio_provider_lookup
            )
        )

        portfolio_conf_service = self.container. \
            portfolio_configuration_service()
        portfolio_snap_service = self.container. \
            portfolio_snapshot_service()
        configuration_service = self.container.configuration_service()
        # Override the order service with the backtest order service
        self.container.order_service.override(
            OrderBacktestService(
                trade_service=self.container.trade_service(),
                order_repository=self.container.order_repository(),
                position_service=self.container.position_service(),
                portfolio_repository=self.container.portfolio_repository(),
                portfolio_configuration_service=portfolio_conf_service,
                portfolio_snapshot_service=portfolio_snap_service,
                configuration_service=configuration_service,
            )
        )

    def initialize_services(self, require_portfolio: bool = True):
        """
        Method to initialize the app. This method should be called before
        running the algorithm. It initializes the services and the algorithm
        and sets up the database if it does not exist.

        Also, it initializes all required services for the algorithm.

        Args:
            require_portfolio (bool): Whether to require a portfolio
                configuration to be present. If True, the app will raise an
                OperationalException if no portfolio is configured.

        Returns:
            None
        """
        logger.info("Initializing services")
        self.initialize_order_executors()
        self.initialize_portfolio_providers()

        # Initialize all market credentials
        market_credential_service = self.container.market_credential_service()
        if require_portfolio:
            market_credential_service.initialize()

        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()

        if require_portfolio and portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        configuration_service = self.container.configuration_service()
        config = configuration_service.get_config()

        self._validate_live_position_modes(
            portfolio_configuration_service, config
        )

        if AppMode.WEB.equals(config[APP_MODE]):
            configuration_service.add_value(APP_MODE, AppMode.WEB.value)
            self._initialize_web()

    def _validate_live_position_modes(
        self, portfolio_configuration_service, config
    ) -> None:
        if Environment.BACKTEST.equals(config[ENVIRONMENT]):
            return

        order_executors = self.container.order_executor_lookup().get_all()
        portfolio_providers = self.container \
            .portfolio_provider_lookup().get_all()

        for configuration in portfolio_configuration_service.get_all():
            if configuration.position_mode != PositionMode.HEDGE:
                continue

            market = configuration.market
            executors = sorted(
                (
                    executor for executor in order_executors
                    if executor.supports_market(market)
                ),
                key=lambda executor: executor.priority,
            )
            providers = sorted(
                (
                    provider for provider in portfolio_providers
                    if provider.supports_market(market)
                ),
                key=lambda provider: provider.priority,
            )
            missing = []
            if not executors:
                missing.append("no order executor supports the venue")
            elif not executors[0].supports_position_mode(
                market, PositionMode.HEDGE
            ):
                missing.append(
                    f"{executors[0].__class__.__name__} cannot route "
                    "directional HEDGE orders"
                )
            if not providers:
                missing.append("no portfolio provider supports the venue")
            elif not providers[0].supports_position_mode(
                market, PositionMode.HEDGE
            ):
                missing.append(
                    f"{providers[0].__class__.__name__} cannot reconcile "
                    "independent HEDGE legs"
                )

            if missing:
                raise OperationalException(
                    f"Live PositionMode.HEDGE is unavailable for portfolio "
                    f"{configuration.identifier} ({market}): "
                    f"{'; '.join(missing)}. Use PositionMode.NETTING, run "
                    "HEDGE in a backtest, or register HEDGE-capable order "
                    "and portfolio adapters."
                )

    def _bind_algorithm_control_persistence(self):
        """
        Wires the algorithm runner's enabled/disabled control file to
        this app's resource directory (and state handler, if any).
        Safe to call multiple times/from multiple entry points
        (``run()``, ``start_algorithm()``, ``stop_algorithm()``,
        ``is_algorithm_enabled()``) since it just re-binds the same
        path.
        """
        algorithm_runner = self.container.algorithm_runner()
        algorithm_runner.bind_persistence(
            self.resource_directory_path, state_handler=self._state_handler
        )
        return algorithm_runner

    def start_algorithm(self) -> bool:
        """
        Enables the algorithm and, if it is currently running live in
        this process, resumes it. In a stateless deployment (AWS
        Lambda, Azure Functions) there is no in-process loop to
        resume — enabling it here is enough, since ``run()`` checks
        this same persisted flag on every future invocation.

        Returns:
            bool: True if an in-process loop was (re)started, False
                otherwise (already running, or no live loop to
                resume).
        """
        algorithm_runner = self._bind_algorithm_control_persistence()

        try:
            return algorithm_runner.start()
        except OperationalException:
            # No live event loop configured yet (e.g. this app has
            # never called `run()` in this process, or it's a
            # stateless deployment) — persisting 'enabled' is enough.
            algorithm_runner.enable()
            return False

    def stop_algorithm(self, reason: str = None, wait: bool = False) -> bool:
        """
        Disables the algorithm and, if it is currently running live in
        this process, signals it to stop after its current iteration.
        In a stateless deployment (AWS Lambda, Azure Functions), this
        persists 'disabled' so the next scheduled invocation of
        ``run()`` skips its iteration entirely.

        Args:
            reason: Optional human-readable reason to persist
                alongside the disabled state.
            wait: If True, blocks until the in-process loop (if any)
                has actually exited.

        Returns:
            bool: True if an in-process loop was signaled to stop,
                False otherwise (it wasn't running).
        """
        algorithm_runner = self._bind_algorithm_control_persistence()
        return algorithm_runner.stop(reason=reason, wait=wait)

    def is_algorithm_enabled(self) -> bool:
        """Returns whether the algorithm is currently enabled."""
        return self._bind_algorithm_control_persistence().is_enabled()

    def get_algorithm_control_state(self) -> dict:
        """Returns the persisted enabled/disabled control state."""
        return self._bind_algorithm_control_persistence().get_control_state()

    def run(
        self,
        number_of_iterations: int = None,
        run_immediately_on_start: bool = True,
    ):
        """
        Entry point to run the application. This method should be called to
        start the trading bot. This method can be called in three modes:

        - Without any params: In this mode, the app runs until a keyboard
        interrupt is received. This mode is useful when running the app in
        a loop.
        - With a payload: In this mode, the app runs only once with the
        payload provided. This mode is useful when running the app in a
        one-off mode, such as running the app from the command line or
        on a schedule. Payload is a dictionary that contains the data to
        handle for the algorithm. This data should look like this:
        {
            "action": "RUN_STRATEGY",
        }
        - With a number of iterations: In this mode, the app runs for the
        number of iterations provided. This mode is useful when running the
        app in a loop for a fixed number of iterations.

        This function first checks if there is an algorithm registered.
         If not, it raises an OperationalException. Then it
         initializes the algorithm with the services and the configuration.

        Args:
            number_of_iterations (int): The number of iterations to run the
                algorithm for
            run_immediately_on_start (bool): When True (default), every
                strategy evaluates on the very first tick regardless of
                its configured schedule (there is no prior run yet to
                compare against). Set to False to instead wait for each
                strategy's normal interval to elapse before its first
                run — e.g. a strategy scheduled every 2 hours would only
                run for the first time 2 hours after startup.

        Returns:
            None
        """
        self.initialize_config()

        # Run all on_initialize hooks
        for hook in self._on_initialize_hooks:
            logger.info(
                f"Running on_initialize hook: {hook.__class__.__name__}"
            )
            hook.on_run(self.context)

        # Load the state if a state handler is provided
        if self._state_handler is not None:
            logger.info("Detected state handler, loading state")
            self._state_handler.initialize()
            config = self.container.configuration_service().get_config()
            self._state_handler.load(config[RESOURCE_DIRECTORY])

        algorithm_runner = self._bind_algorithm_control_persistence()

        if not algorithm_runner.is_enabled():
            control_state = algorithm_runner.get_control_state()
            logger.info(
                "Algorithm is disabled (stopped via the control API "
                f"or control file, reason: {control_state.get('reason')})"
                " — skipping this run."
            )
            return

        self.initialize_storage()
        logger.info("App initialization complete")
        event_loop_service = None
        run_started_at = datetime.now(timezone.utc)

        try:
            # Run all on_after_initialize hooks
            for hook in self._on_after_initialize_hooks:
                logger.info(
                    f"Running on_after_initialize "
                    f"hook: {hook.__class__.__name__}"
                )
                hook.on_run(self.context)

            algorithm = self.get_algorithm()
            self.initialize_data_sources(algorithm.data_sources)
            self.initialize_services()
            self.initialize_portfolios()
            self._log_next_scheduled_runs(
                algorithm, run_immediately_on_start=run_immediately_on_start
            )

            is_live_web_run = AppMode.WEB.equals(self.config[APP_MODE]) \
                and not self._web_app_testing \
                and number_of_iterations is None
            web_thread = None

            if is_live_web_run:
                web_port = 8080
                logger.info(
                    f"Running web — API: http://localhost:{web_port} "
                    f"— Swagger docs: http://localhost:{web_port}/docs"
                )
                web_thread = threading.Thread(
                    name='Web App',
                    target=uvicorn.run,
                    args=(self._web_app,),
                    kwargs={
                        "host": "0.0.0.0",
                        "port": web_port,
                        # Skip uvicorn's own logging setup (its
                        # "INFO:     ..." banner/access logs) — we
                        # already log a nicer, consistently formatted
                        # startup line above. Its loggers fall back to
                        # propagating to the root logger instead.
                        "log_config": None,
                    },
                )
                web_thread.daemon = True
                web_thread.start()

            trade_order_evaluator = DefaultTradeOrderEvaluator(
                trade_service=self.container.trade_service(),
                order_service=self.container.order_service(),
                trade_stop_loss_service=self.container
                .trade_stop_loss_service(),
                trade_take_profit_service=self.container
                .trade_take_profit_service(),
                configuration_service=self.container.configuration_service(),
                blotter=self._blotter,
                context=self.context
            )
            event_loop_service = EventLoopService(
                configuration_service=self.container.configuration_service(),
                portfolio_snapshot_service=self.container
                .portfolio_snapshot_service(),
                context=self.context,
                order_service=self.container.order_service(),
                portfolio_service=self.container.portfolio_service(),
                data_provider_service=self.container.data_provider_service(),
                trade_service=self.container.trade_service(),
            )
            event_loop_service.initialize(
                algorithm, trade_order_evaluator=trade_order_evaluator,
                run_immediately_on_start=run_immediately_on_start,
            )

            if number_of_iterations is None:
                logger.info("Startup complete — entering live loop")

                # Continuous runs never naturally "finish", so build
                # and persist a RunReport after every tick that
                # actually ran a strategy — not just once when the
                # loop eventually stops.
                def _build_iteration_run_report(strategies):
                    self._last_run_report = self._build_run_report(
                        event_loop_service, run_started_at,
                        algorithm=algorithm, number_of_iterations=None,
                    )

                event_loop_service.on_iteration_complete = \
                    _build_iteration_run_report
            else:
                logger.info(
                    "Startup complete — running "
                    f"{number_of_iterations} iteration(s)"
                )

            if is_live_web_run:
                # Run the event loop in its own background thread so
                # the web API can start/stop it on demand (see
                # `/api/algorithm/start` and `/api/algorithm/stop`)
                # without killing the process. The main thread just
                # keeps the process alive alongside the web thread.
                def _build_web_run_report():
                    self._last_run_report = self._build_run_report(
                        event_loop_service, run_started_at,
                        algorithm=algorithm, number_of_iterations=None,
                    )

                algorithm_runner.configure(
                    event_loop_service, on_stop=_build_web_run_report
                )
                algorithm_runner.start()

                try:
                    while web_thread.is_alive():
                        web_thread.join(timeout=1)
                except KeyboardInterrupt:
                    # A local Ctrl+C is a process shutdown, not a
                    # deliberate "stop trading" decision — don't
                    # persist 'disabled' or the next `python
                    # test.py` run would silently skip.
                    algorithm_runner.stop(wait=True, persist=False)
                    exit(0)
            else:
                try:
                    event_loop_service.start(
                        number_of_iterations=number_of_iterations
                    )
                    self._last_run_report = self._build_run_report(
                        event_loop_service, run_started_at,
                        algorithm=algorithm,
                        number_of_iterations=number_of_iterations,
                    )
                except KeyboardInterrupt:
                    exit(0)
        except Exception as e:
            logger.error(e)
            raise e
        finally:

            if event_loop_service is not None:
                self._run_history = event_loop_service.history

            try:
                # Upload state if state handler is provided
                if self._state_handler is not None:
                    logger.info("Detected state handler, saving state")
                    config = \
                        self.container.configuration_service().get_config()
                    self._state_handler.save(config[RESOURCE_DIRECTORY])
            except Exception as e:
                logger.error(e)

    def validate(self, require_portfolio: bool = True) -> None:
        """
        Runs the same setup `run()` performs before entering its live
        event loop (config, hooks, storage, algorithm resolution, data
        sources, services, portfolios), then returns.

        Meant to be called by tooling that has already imported an
        entry module (e.g. an `app.py` built via `create_app()` +
        `add_strategy(...)` + `add_market(...)`) and obtained its
        `App` instance — not by the entry file itself, since
        `if __name__ == "__main__": app.run()` never fires on import.

        Never starts EventLoopService, never starts the web thread,
        executes no strategy iterations, places no orders.

        Args:
            require_portfolio (bool): When True (default), also runs
                `initialize_portfolios()`, so a configured market/portfolio
                and resolvable market credentials are required, matching
                `run()` exactly. Set to False to initialize services,
                including configured market credentials, without requiring
                a portfolio or a credential for any market.

        Raises:
            Exception: Any exception raised during config, hook,
                algorithm, data source, or (when `require_portfolio`
                is True) service/portfolio initialization.
        """
        self.initialize_config()

        for hook in self._on_initialize_hooks:
            hook.on_run(self.context)

        self.initialize_storage()
        algorithm = self.get_algorithm()
        self.initialize_data_sources(algorithm.data_sources)

        self.initialize_services(require_portfolio=require_portfolio)

        if require_portfolio:
            self.initialize_portfolios()

    def add_portfolio_configuration(self, portfolio_configuration):
        """
        Function to add a portfolio configuration to the app. The portfolio
        configuration should be an instance of PortfolioConfiguration.

        Args:
            portfolio_configuration: Instance of PortfolioConfiguration

        Returns:
            None
        """
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.add(portfolio_configuration)

    def task(
        self,
        function=None,
        schedule: Schedule = None,
    ):
        """
        Function to add a task to the application.

        Args:
            function: the decorated function (when used as ``@app.task``).
            schedule: required :class:`Schedule` describing when to fire.
                Build with ``Schedule.every(interval, time_unit)`` or
                ``Schedule.on(date_rule, time_rule)``.

        Returns:
            Union(Task, Function): the task
        """
        if schedule is None:
            raise OperationalException(
                "@app.task requires a ``schedule=`` argument. Use "
                "``Schedule.every(interval, time_unit)``. The legacy "
                "``time_unit=``/``interval=`` kwargs were removed in v9.0."
            )
        if not isinstance(schedule, Schedule):
            raise OperationalException(
                f"@app.task ``schedule=`` must be a Schedule instance; "
                f"got {type(schedule).__name__}."
            )

        if function:
            task = Task(
                decorated=function,
                schedule=schedule,
            )
            self._tasks.append(task)
            return task
        else:
            def wrapper(f):
                self._tasks.append(
                    Task(
                        decorated=f,
                        schedule=schedule,
                    )
                )
                return f

            return wrapper

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        assert isinstance(task, Task), OperationalException(
            "Task object is not an instance of a Task"
        )

        self._tasks.append(task)

    def add_tasks(self, tasks: List[Task]):
        """
        Function to add a list of tasks to the app. The tasks should be
        instances of Task.

        Args:
            tasks: List of Task instances

        Returns:
            None
        """
        for task in tasks:
            self.add_task(task)

    def _initialize_web(self):
        """
        Initialize the app for web mode by setting the configuration
        parameters for web mode and overriding the services with the
        web services equivalents.

        Web has the following implications:
        - db
            - sqlite
        - services
            - FastAPI app
            - Investing Algorithm Framework App
            - Algorithm
        """
        configuration_service = self.container.configuration_service()
        self._web_app = create_fastapi_app(configuration_service)

    def get_portfolio_configurations(self):
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        return portfolio_configuration_service.get_all()

    def get_market_credential(self, market: str) -> MarketCredential:
        """
        Function to get a market credential from the app. This method
        should be called when you want to get a market credential.

        Args:
            market (str): The market to get the credential for

        Returns:
            MarketCredential: Instance of MarketCredential
        """

        market_credential_service = self.container \
            .market_credential_service()
        market_credential = market_credential_service.get(market)
        if market_credential is None:
            raise OperationalException(
                f"Market credential for {market} not found"
            )
        return market_credential

    def get_market_credentials(self) -> List[MarketCredential]:
        """
        Function to get all market credentials from the app. This method
        should be called when you want to get all market credentials.

        Returns:
            List of MarketCredential instances
        """
        market_credential_service = self.container \
            .market_credential_service()
        return market_credential_service.get_all()

    def check_data_completeness(
        self,
        strategies: List[TradingStrategy],
        backtest_date_range: BacktestDateRange,
        show_progress: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Function to check the data completeness for a set of strategies
        over a given backtest date range. This method checks if all data
        sources required by the strategies have complete data for the
        specified date range.

        Args:
            strategies (List[TradingStrategy]): List of strategy objects
                to check data completeness for.
            backtest_date_range (BacktestDateRange): The date range to
                check data completeness for.
            show_progress (bool): Whether to show a progress bar when
                checking data completeness.
        Returns:
            Tuple[bool, Dict[str, Any]]: A tuple containing a boolean
                indicating if the data is complete and a dictionary
                with information about missing data for each data source.
        """
        data_sources = []
        missing_data_info = {}

        for strategy in strategies:
            data_sources.extend(strategy.data_sources)

        self.initialize_data_sources_backtest(
            data_sources,
            backtest_date_range,
            show_progress=show_progress
        )
        data_provider_service = self.container.data_provider_service()
        unique_data_sources = set(data_sources)

        for data_source in unique_data_sources:

            if DataType.OHLCV.equals(data_source.data_type):
                required_start_date = backtest_date_range.start_date - \
                    timedelta(
                        minutes=TimeFrame.from_value(
                            data_source.time_frame
                        ).amount_of_minutes * data_source.window_size
                    )
                number_of_required_data_points = \
                    data_source.get_number_of_required_data_points(
                        backtest_date_range.start_date,
                        backtest_date_range.end_date
                    )

                try:
                    data_provider = data_provider_service.get(data_source)
                    number_of_available_data_points = \
                        data_provider.get_number_of_data_points(
                            backtest_date_range.start_date,
                            backtest_date_range.end_date
                        )

                    missing_dates = \
                        data_provider.get_missing_data_dates(
                            required_start_date,
                            backtest_date_range.end_date
                        )
                    if len(missing_dates) > 0:
                        missing_data_info[data_source.identifier] = {
                            "data_source_id": data_source.identifier,
                            "completeness_percentage": (
                                (
                                    number_of_available_data_points /
                                    number_of_required_data_points
                                ) * 100
                            ),
                            "missing_data_points": len(
                                missing_dates
                            ),
                            "missing_dates": missing_dates,
                            "data_source_file_path":
                                data_provider.get_data_source_file_path()
                        }

                except Exception as e:
                    raise DataError(
                        f"Error getting data provider for data source "
                        f"{data_source.identifier} "
                        f"({data_source.symbol}): {str(e)}"
                    )

        if len(missing_data_info.keys()) > 0:
            return False, missing_data_info

        return True, missing_data_info

    def get_backtest_data(  # noqa: F811
        self,
        strategy: TradingStrategy,
        backtest_date_range: BacktestDateRange,
        show_progress: bool = False,
        fill_missing_data: bool = True,
    ) -> Dict[str, Any]:
        """
        Get all data sources with their corresponding data for a given
        strategy and backtest window.

        This method retrieves the market data for all data sources defined
        in the strategy, considering the warmup window for each data source.
        The data is returned as a dictionary where keys are data source
        identifiers and values are the corresponding DataFrames.

        Args:
            strategy (TradingStrategy): The strategy containing the data
                sources to retrieve data for.
            backtest_date_range (BacktestDateRange): The date range for
                the backtest window.
            show_progress (bool): Whether to show progress bars during
                data retrieval. Defaults to True.
            fill_missing_data (bool): If True, missing time series data
                entries will be filled automatically. Defaults to True.

        Returns:
            Dict[str, Any]: A dictionary where keys are data source
                identifiers (e.g., "BTC/EUR_ohlcv") and values are the
                corresponding data (typically pandas DataFrames).

        Example:
            ```python
            from investing_algorithm_framework import (
                create_app, TradingStrategy, BacktestDateRange, DataSource
            )
            from datetime import datetime, timezone

            class MyStrategy(TradingStrategy):
                data_sources = [
                    DataSource(
                        identifier="btc_data",
                        symbol="BTC/EUR",
                        time_frame="1h",
                        warmup_window=100,
                        market="BITVAVO"
                    )
                ]
                # ... strategy implementation

            app = create_app()
            app.add_strategy(MyStrategy)

            backtest_range = BacktestDateRange(
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
            )

            # Get all data for the strategy
            data = app.get_backtest_data(
                strategy=MyStrategy(),
                backtest_date_range=backtest_range
            )

            # Access data by identifier
            btc_df = data["btc_data"]
            ```

        Raises:
            OperationalException: If no data sources are defined in the
                strategy or if data cannot be retrieved for a data source.
        """
        # Get data sources from the strategy
        data_sources = strategy.data_sources

        if data_sources is None or len(data_sources) == 0:
            raise OperationalException(
                "No data sources defined in the strategy. "
                "Please define data sources to retrieve backtest data."
            )

        # Setup backtest data providers
        self.initialize_data_sources_backtest(
            data_sources=data_sources,
            backtest_date_range=backtest_date_range,
            show_progress=show_progress,
            fill_missing_data=fill_missing_data,
        )

        # Get the data provider service
        data_provider_service = self.container.data_provider_service()

        # Retrieve vectorized backtest data for all data sources
        data = data_provider_service.get_vectorized_backtest_data(
            data_sources=data_sources,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date,
        )

        return data

    def run_backtest(
        self,
        strategy: Optional[TradingStrategy] = None,
        strategies: Optional[List[TradingStrategy]] = None,
        algorithms: Optional[List[Algorithm]] = None,
        study: Optional[Study] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        skip_data_sources_initialization: bool = False,
        show_progress: bool = False,
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
        n_workers: Optional[int] = None,
        dynamic_position_sizing: bool = False,
        fill_missing_data: bool = True,
        iterative_summary_update: bool = False,
        anchor_algorithm_id: Optional[str] = None,
        algorithm=None,
    ) -> List[Backtest]:
        """
        Run a backtest for one or more strategies using a Study as
        configuration.

        The Study provides the universe (which carries risk-free rate and
        initial capital), backtest windows, and study name / description.
        The engine (vectorized vs event-driven) is selected automatically:
        strategies implementing ``generate_signal_series`` use the
        vectorized engine; all others use the event-driven engine.

        Exactly one of ``strategy=``, ``strategies=``, ``algorithm=`` or
        ``algorithms=`` should be provided (falls back to the app's
        registered strategies when none are given).

        Args:
            strategy: A single strategy to backtest.
            strategies: Multiple strategies; each yields one Backtest
                (independent backtests, for comparison — each strategy
                gets its own portfolio).
            algorithm: An Algorithm whose strategies should all be
                backtested TOGETHER, sharing one portfolio, in ONE
                Backtest — the backtest-mode equivalent of how
                ``app.run()`` executes multiple strategies live.
                Mutually exclusive with ``strategy=``/``strategies=``/
                ``algorithms=``. Currently only supported by the
                event-driven engine; raises ``OperationalException`` if
                the algorithm has more than one strategy and resolves to
                the vector engine.
            algorithms: Multiple Algorithms, each run independently
                (own portfolio, own combined Backtest) — the multi-
                algorithm equivalent of ``strategies=``. Mutually
                exclusive with ``strategy=``/``strategies=``/
                ``algorithm=``. Only supported by the event-driven
                engine.
            study: Study configuration — provides ``universe``,
                ``backtest_windows``, ``name``, ``description`` and
                ``window_part`` (which part of each window to run —
                ``"train"``, ``"test"`` or ``"both"``, see
                :class:`WindowPart`). Required.
            snapshot_interval: Portfolio snapshot frequency.
            skip_data_sources_initialization: Skip data provider init when
                data is already cached.
            show_progress: Show progress bars during execution.
            continue_on_error: If True, continue instead of raising on
                individual backtest errors.
            window_filter_function: Filter applied after each date range.
            final_filter_function: Filter applied after all windows.
            backtest_storage_directory: Directory for persisting backtest
                files.
            use_checkpoints: Resume interrupted runs from saved checkpoints.
            batch_size: Strategies per batch when use_checkpoints=True.
            checkpoint_batch_size: Backtests saved per checkpoint flush.
            n_workers: Parallel workers (None=sequential, -1=all cores).
            dynamic_position_sizing: Enable volatility-scaled position sizing.
            fill_missing_data: Auto-fill missing OHLCV rows.
            iterative_summary_update: Update summary after each window.
            anchor_algorithm_id: Reference algorithm for relative metrics.

        Returns:
            List[Backtest]: One Backtest per strategy, ordered to match
                the input strategies list, when ``strategy=``/
                ``strategies=`` is used. When ``algorithm=`` is used,
                a list with exactly one combined Backtest.

        Raises:
            OperationalException: If study is missing, has no
                backtest_windows, or no strategy can be resolved. Also
                raised when ``algorithm=``/``algorithms=`` resolves to
                the vector engine (not supported), or when more than one
                of ``strategy=``/``strategies=``/``algorithm=``/
                ``algorithms=`` is provided at once.
        """
        _modes_given = sum(
            1 for v in (
                strategy is not None,
                strategies is not None,
                algorithm is not None,
                algorithms is not None,
            ) if v
        )
        if _modes_given > 1:
            raise OperationalException(
                "Provide only one of strategy=, strategies=, algorithm= "
                "or algorithms= to run_backtest."
            )

        # Combined-algorithm mode: run every strategy on `algorithm`
        # together in ONE backtest sharing one portfolio (mirrors how
        # `app.run()` executes multiple strategies live). Mutually
        # exclusive with strategy=/strategies=/algorithms=, which
        # instead run each strategy/algorithm as its own independent
        # backtest for comparison.
        combined_algorithm = None

        if algorithm is not None:
            algorithm_factory = self.container.algorithm_factory()
            combined_algorithm = algorithm_factory.create_algorithm(
                algorithm=algorithm
            )

            if len(combined_algorithm.strategies) == 0:
                raise OperationalException(
                    "The provided algorithm has no strategies registered. "
                    "Add at least one strategy before calling run_backtest."
                )

        # Independent-algorithms mode: each Algorithm runs on its own
        # portfolio, yielding its own Backtest (the Algorithm-level
        # equivalent of strategies=).
        independent_algorithms = None

        if algorithms is not None:
            independent_algorithms = list(algorithms)
            if not independent_algorithms:
                raise OperationalException(
                    "algorithms= was provided but is empty. Provide at "
                    "least one Algorithm, or omit algorithms=."
                )

        if study is None:
            raise OperationalException(
                "run_backtest requires a Study. "
                "Pass a Study instance with backtest_windows and "
                "a universe configured."
            )

        if study.universe is None:
            raise OperationalException(
                "Study must have a universe configured. "
                "Pass a Study instance with a universe configured."
            )

        if study.backtest_windows is None or len(study.backtest_windows) == 0:
            raise OperationalException(
                "Study must have at least one backtest window configured. "
                "Pass a Study instance with backtest_windows configured."
            )

        if study.engine is None:
            # No engine set — will be auto-detected from the strategy below
            pass

        # Normalise strategy / strategies / algorithm / algorithms into
        # a single flat list of strategies (used for engine detection
        # and universe injection).
        if independent_algorithms is not None:
            strats: List[TradingStrategy] = [
                s for alg in independent_algorithms for s in alg.strategies
            ]
            if not strats:
                raise OperationalException(
                    "None of the provided algorithms have strategies "
                    "registered. Add at least one strategy to each "
                    "algorithm before calling run_backtest."
                )
        elif combined_algorithm is not None:
            strats: List[TradingStrategy] = list(
                combined_algorithm.strategies
            )
        else:
            strats = []

            if strategy is not None:
                strats.append(strategy)
            if strategies:
                strats.extend(s for s in strategies if s is not strategy)
            if not strats:
                if self._strategies:
                    strats = list(self._strategies)
                else:
                    raise OperationalException(
                        "No strategy provided and no strategies "
                        "registered. Please provide a strategy or "
                        "register one before calling run_backtest."
                    )

            # Instantiate strategy classes and ensure all have an
            # algorithm_id
            instantiated = []
            for s in strats:
                if inspect.isclass(s):
                    s = s()
                if not hasattr(s, "algorithm_id") or s.algorithm_id is None:
                    s.algorithm_id = generate_algorithm_id(strategy=s)
                instantiated.append(s)
            strats = instantiated

        # Extract configuration from the Study
        universe = study.universe
        engine = study.engine
        risk_free_rate = study.risk_free_rate

        # Resolve each window to the range(s) that should run, per
        # study.window_part ("train" / "test" / "both").
        backtest_date_ranges = study.resolve_backtest_date_ranges()

        if not backtest_date_ranges:
            raise OperationalException(
                "Could not resolve any date ranges from "
                "study.backtest_windows. Each BacktestWindow must have "
                "a train_range or test_range."
            )

        if use_checkpoints and backtest_storage_directory is None:
            raise OperationalException(
                "backtest_storage_directory must be provided when "
                "use_checkpoints is set to True"
            )

        # Engine selection priority:
        #   1. Explicit study.engine value (VECTOR or EVENT) is respected.
        #   2. Auto-detect when study.engine is None:
        #      vectorized only if every strategy overrides
        #      generate_signal_series and none override generate_signals.
        _base_gss = TradingStrategy.generate_signal_series
        _base_gs = TradingStrategy.generate_signals
        if engine == BacktestEngine.VECTOR:
            use_vector = True
        elif engine == BacktestEngine.EVENT_DRIVEN:
            use_vector = False
        else:
            use_vector = (
                all(
                    type(s).generate_signal_series is not _base_gss
                    for s in strats
                )
                and all(type(s).generate_signals is _base_gs for s in strats)
            )

        if use_vector and combined_algorithm is not None \
                and len(strats) > 1:
            raise OperationalException(
                "Combined multi-strategy backtests (an `algorithm=` with "
                "more than one strategy, run together sharing one "
                "portfolio) are only supported by the event-driven "
                "engine right now. Either set "
                "study.engine=BacktestEngine.EVENT_DRIVEN, implement "
                "generate_signals(...) instead of "
                "generate_signal_series(...) on your strategies, or "
                "backtest each strategy independently via strategy=/"
                "strategies=."
            )

        if use_vector and independent_algorithms is not None:
            raise OperationalException(
                "algorithms= (independent Algorithms, each with its own "
                "Tasks/hooks) is only supported by the event-driven "
                "engine. Set study.engine=BacktestEngine.EVENT_DRIVEN, "
                "implement generate_signals(...) instead of "
                "generate_signal_series(...) on your strategies, or "
                "backtest each strategy independently via strategy=/"
                "strategies=."
            )

        if use_vector:
            if not skip_data_sources_initialization:
                data_provider_service = (
                    self.container.data_provider_service()
                )
                data_provider_service.reset()

                for dp_tuple in self._data_providers:
                    data_provider_service.add_data_provider(
                        dp_tuple[0], priority=dp_tuple[1]
                    )
                data_provider_service.add_data_provider(
                    CCXTOHLCVDataProvider()
                )

            # Build portfolio configuration from universe when possible
            if (
                universe is not None
                and study.initial_capital is not None
                and universe.market is not None
                and universe.trading_symbol is not None
            ):
                portfolio_configuration = PortfolioConfiguration(
                    initial_balance=study.initial_capital,
                    market=universe.market,
                    trading_symbol=universe.trading_symbol,
                )
            else:
                portfolio_configurations = (
                    self.get_portfolio_configurations()
                )
                if not portfolio_configurations:
                    raise OperationalException(
                        "No portfolio configuration found. "
                        "Set study.initial_capital, universe.market "
                        "and universe.trading_symbol on the Study, or "
                        "add a portfolio configuration to the app before "
                        "calling run_backtest."
                    )
                portfolio_configuration = portfolio_configurations[0]
                if study.initial_capital is not None:
                    portfolio_configuration.initial_balance = (
                        study.initial_capital
                    )

            backtest_service: BacktestService = (
                self.container.backtest_service()
            )
            backtests = backtest_service.run_vector_backtests(
                strategies=strats,
                study=study,
                snapshot_interval=snapshot_interval,
                skip_data_sources_initialization=(
                    skip_data_sources_initialization
                ),
                show_progress=show_progress,
                continue_on_error=continue_on_error,
                backtest_storage_directory=backtest_storage_directory,
                window_filter_function=window_filter_function,
                final_filter_function=final_filter_function,
                batch_size=batch_size,
                checkpoint_batch_size=checkpoint_batch_size,
                n_workers=n_workers,
                use_checkpoints=use_checkpoints,
                dynamic_position_sizing=dynamic_position_sizing,
                fill_missing_data=fill_missing_data,
                iterative_summary_update=iterative_summary_update,
            )
            # Note: unlike the event-driven branch below,
            # backtest_service.run_vector_backtests() is already
            # Study-native and stamps backtest_windows onto the
            # correct (named) study itself. Re-stamping here via
            # _apply_backtest_windows() would call
            # _get_or_create_default_study() on a fresh in-memory
            # Backtest whose ``_studies`` dict may not yet reflect
            # what's on disk, and the subsequent merge-on-save could
            # introduce a spurious extra "default" study slot.
        else:
            # ── Event-driven engine ───────────────────────────────────
            first_date_range = backtest_date_ranges[0]

            initial_capital = study.initial_capital
            self.initialize_backtest_config(
                backtest_date_range=first_date_range,
                snapshot_interval=snapshot_interval,
                initial_amount=initial_capital,
            )
            self.initialize_storage(remove_database_if_exists=True)
            self.initialize_backtest_services()
            self.initialize_backtest_portfolios()

            data_provider_service = self.container.data_provider_service()
            data_provider_service.reset()
            for dp_tuple in self._data_providers:
                data_provider_service.add_data_provider(
                    dp_tuple[0], priority=dp_tuple[1]
                )
            data_provider_service.add_data_provider(CCXTOHLCVDataProvider())

            # Inject universe fields into strategies that do not set them.
            if universe is not None:
                _u_map = _build_strategy_universe_map(strats, universe)
                for _s in strats:
                    _matched = _u_map.get(_s.algorithm_id)
                    if _matched is None:
                        continue
                    if not _s.symbols and _matched.symbols:
                        _s.symbols = list(_matched.symbols)
                    if not getattr(_s, "market", None) and _matched.market:
                        _s.market = _matched.market

            algorithm_factory = self.container.algorithm_factory()

            if independent_algorithms is not None:
                final_algorithms = independent_algorithms
            elif combined_algorithm is not None:
                final_algorithms = [combined_algorithm]
            else:
                final_algorithms = []
                for strat in strats:
                    alg = algorithm_factory.create_algorithm(
                        strategy=strat,
                        tasks=self._tasks,
                        on_strategy_run_hooks=self._on_strategy_run_hooks,
                    )
                    final_algorithms.append(alg)

            backtest_service = self.container.backtest_service()
            backtests = backtest_service.run_backtests(
                algorithms=final_algorithms,
                context=self.context,
                trade_stop_loss_service=(
                    self.container.trade_stop_loss_service()
                ),
                trade_take_profit_service=(
                    self.container.trade_take_profit_service()
                ),
                backtest_date_ranges=backtest_date_ranges,
                risk_free_rate=risk_free_rate,
                skip_data_sources_initialization=False,
                show_progress=show_progress,
                continue_on_error=continue_on_error,
                window_filter_function=window_filter_function,
                final_filter_function=final_filter_function,
                backtest_storage_directory=backtest_storage_directory,
                use_checkpoints=use_checkpoints,
                batch_size=batch_size,
                checkpoint_batch_size=checkpoint_batch_size,
                fill_missing_data=fill_missing_data,
                iterative_summary_update=iterative_summary_update,
                blotter=self._blotter,
            )

            _apply_study_to_backtests(
                backtests,
                study,
                [s for alg in final_algorithms for s in alg.strategies],
                backtest_storage_directory,
                anchor_algorithm_id=anchor_algorithm_id,
            )
            self.cleanup_backtest_resources()

        return backtests

    def run_backtests(
        self,
        strategies: List[TradingStrategy] = None,
        algorithms: List[Algorithm] = None,
        study: Optional[Study] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        skip_data_sources_initialization: bool = False,
        show_progress: bool = False,
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
        n_workers: Optional[int] = None,
        dynamic_position_sizing: bool = False,
        fill_missing_data: bool = True,
        iterative_summary_update: bool = False,
    ) -> List[Backtest]:
        """
        Sweep multiple independent strategies (or algorithms) over a
        Study, comparing results. Each strategy/algorithm gets its own
        portfolio and yields its own Backtest. Thin wrapper around
        :meth:`run_backtest` — the engine (vectorized vs event-driven)
        is auto-detected the same way.

        Exactly one of ``strategies=``/``algorithms=`` should be
        provided (falls back to the app's registered strategies when
        neither is given).

        Args:
            strategies: The strategies to backtest independently.
            algorithms: The algorithms to backtest independently (each
                with its own portfolio) — only supported by the
                event-driven engine. Mutually exclusive with
                ``strategies=``.
            study: Study configuration — provides ``universe``,
                ``backtest_windows`` (one or more), ``name``,
                ``description`` and ``window_part``. Required.
            snapshot_interval: Portfolio snapshot frequency.
            skip_data_sources_initialization: Skip data provider init when
                data is already cached.
            show_progress: Show progress bars during execution.
            continue_on_error: If True, continue instead of raising on
                individual backtest errors.
            window_filter_function: Filter applied after each date range;
                only surviving strategies continue to the next window.
            final_filter_function: Filter applied after all windows.
            backtest_storage_directory: Directory for persisting backtest
                files.
            use_checkpoints: Resume interrupted runs from saved checkpoints.
            batch_size: Strategies per batch when use_checkpoints=True.
            checkpoint_batch_size: Backtests saved per checkpoint flush.
            n_workers: Parallel workers (None=sequential, -1=all cores).
                Only used by the vectorized engine.
            dynamic_position_sizing: Enable volatility-scaled position sizing.
            fill_missing_data: Auto-fill missing OHLCV rows.
            iterative_summary_update: Update summary after each window.

        Returns:
            List[Backtest]: One Backtest per strategy/algorithm (per
            surviving one, if filter functions are provided).
        """
        return self.run_backtest(
            strategies=strategies,
            algorithms=algorithms,
            study=study,
            snapshot_interval=snapshot_interval,
            skip_data_sources_initialization=skip_data_sources_initialization,
            show_progress=show_progress,
            continue_on_error=continue_on_error,
            window_filter_function=window_filter_function,
            final_filter_function=final_filter_function,
            backtest_storage_directory=backtest_storage_directory,
            use_checkpoints=use_checkpoints,
            batch_size=batch_size,
            checkpoint_batch_size=checkpoint_batch_size,
            n_workers=n_workers,
            dynamic_position_sizing=dynamic_position_sizing,
            fill_missing_data=fill_missing_data,
            iterative_summary_update=iterative_summary_update,
        )

    def run_monte_carlo_test(
        self,
        strategy: TradingStrategy,
        backtest_date_range: BacktestDateRange,
        number_of_permutations: int = 100,
        initial_amount: float = 1000.0,
        market: str = None,
        trading_symbol: str = None,
        risk_free_rate: Optional[float] = None,
        show_progress: bool = True,
    ) -> BacktestMonteCarloTest:
        """
        Run a Monte-Carlo significance test for a given strategy over a
        specified date range. This test is used to determine the statistical
        significance of the strategy's performance by comparing it
        against a set of random permutations of the market data.

        The Monte-Carlo test will run the main backtest and then
        generate a number of random permutations of the market data
        to create a distribution of returns. The p value will be
        calculated based on the performance of the main backtest
        compared to the distribution of returns from the permutations.

        Args:
            strategy (TradingStrategy): The strategy to test.
            backtest_date_range (BacktestDateRange): The date range for the
                backtest.
            number_of_permutations (int): The number of permutations to run.
                Default is 100.
            initial_amount (float): The initial amount for the backtest.
                Default is 1000.0.
            risk_free_rate (Optional[float]): The risk-free rate to use for
                the backtest metrics. If not provided, it will try to fetch
                the risk-free rate from the US Treasury website.
            market (str): The market to use for the backtest. This is used
                to create a portfolio configuration if no portfolio
                configuration is provided in the strategy. If not provided,
                the first portfolio configuration found will be used.
            trading_symbol (str): The trading symbol to use for the backtest.
                This is used to create a portfolio configuration if no
                portfolio configuration is provided in the strategy. If not
                provided, the first trading symbol found in the portfolio
                configuration will be used.
            show_progress (bool): Whether to show a progress bar during
                the Monte-Carlo test. Defaults to True.

        Raises:
            OperationalException: If the risk-free rate cannot be retrieved.

        Returns:
            Backtest: The backtest report containing the results of the
                main backtest and the p value from the Monte-Carlo test.
        """

        if risk_free_rate is None:
            logger.info(
                "No risk free rate provided, defaulting to 0.027 "
                "(2.7%%). Provide risk_free_rate to override."
            )
            risk_free_rate = 0.027

        backtest_service = self.container.backtest_service()
        data_provider_service = self.container.data_provider_service()

        _market = market
        _trading_symbol = trading_symbol

        if _market is None or _trading_symbol is None:
            for pc in self.get_portfolio_configurations():
                if _market is None:
                    _market = pc.market
                if _trading_symbol is None:
                    _trading_symbol = pc.trading_symbol
                break

        study = Study(
            name="monte_carlo",
            universe=Universe(
                market=_market or "", trading_symbol=_trading_symbol or "",
            ),
            initial_capital=initial_amount,
            risk_free_rate=risk_free_rate,
            backtest_windows=[
                BacktestWindow(train_range=backtest_date_range)
            ],
        )
        backtests = self.run_backtest(
            strategy=strategy,
            study=study,
            snapshot_interval=SnapshotInterval.DAILY,
            use_checkpoints=False,
            show_progress=show_progress,
        )
        backtest = backtests[0]
        backtest_metrics = backtest.get_backtest_metrics(backtest_date_range)

        if backtest_metrics.number_of_trades == 0:
            raise OperationalException(
                "The strategy did not make any trades during the backtest. "
                "Cannot perform Monte-Carlo test."
            )

        # Select the ohlcv data from the strategy's data sources
        data_sources = strategy.data_sources
        original_data_combinations = []
        permuted_metrics = []
        permuted_datasets_ordered_by_symbol = {}
        original_datasets_ordered_by_symbol = {}

        for data_source in data_sources:
            if DataType.OHLCV.equals(data_source.data_type):
                data_provider = data_provider_service.get(data_source)
                data = data_provider_service.get_data(
                    data_source=data_source,
                    start_date=data_provider._start_date_data_source,
                    end_date=backtest_date_range.end_date
                )
                original_data_combinations.append((data_source, data))
                original_datasets_ordered_by_symbol[data_source.symbol] = (
                    data_provider_service.get_data(
                        data_source=data_source,
                        start_date=data_provider._start_date_data_source,
                        end_date=backtest_date_range.end_date
                    )
                )

        for _ in tqdm(
            range(number_of_permutations),
            desc="Running Monte-Carlo Test",
            colour="green",
            disable=not show_progress
        ):
            permutated_datasets = []
            data_provider_service.reset()

            for combi in original_data_combinations:
                # Permute the data for the data source
                permutated_data = backtest_service\
                    .create_ohlcv_permutation(data=combi[1])
                permutated_datasets.append((combi[0], permutated_data))

                if combi[0].symbol not in permuted_datasets_ordered_by_symbol:
                    permuted_datasets_ordered_by_symbol[combi[0].symbol] = \
                        [permutated_data]
                else:
                    permuted_datasets_ordered_by_symbol[combi[0].symbol]\
                        .append(permutated_data)

            self._data_providers = []

            for combi in permutated_datasets:
                data_source = combi[0]
                data_provider = PandasOHLCVDataProvider(
                    dataframe=combi[1],
                    symbol=data_source.symbol,
                    market=data_source.market,
                    warmup_window=data_source.warmup_window,
                    time_frame=data_source.time_frame,
                    data_provider_identifier=data_source
                    .data_provider_identifier,
                    pandas=data_source.pandas,
                )
                # Add pandas ohlcv data provider to the data provider service
                data_provider_service.register_data_provider(
                    data_source=data_source,
                    data_provider=data_provider
                )

            # Run the backtest with the permuted strategy
            permuted_backtests = self.run_backtest(
                strategy=strategy,
                study=study,
                snapshot_interval=SnapshotInterval.DAILY,
                skip_data_sources_initialization=True,
                use_checkpoints=False,
                show_progress=show_progress,
            )
            permuted_backtest = permuted_backtests[0]

            # Add the results of the permuted backtest to the main backtest
            permuted_metrics.append(
                permuted_backtest.get_backtest_metrics(backtest_date_range)
            )

        # Create a BacktestMonteCarloTestMetrics object
        monte_carlo_test_metrics = BacktestMonteCarloTest(
            real_metrics=backtest_metrics,
            permutated_metrics=permuted_metrics,
            ohlcv_permutated_datasets=permuted_datasets_ordered_by_symbol,
            ohlcv_original_datasets=original_datasets_ordered_by_symbol,
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name
        )
        return monte_carlo_test_metrics

    def add_data_provider(self, data_provider, priority=3) -> None:
        """
        Function to add a data provider to the app. The data provider should
        be an instance of DataProvider or a DataProviderClass.

        Args:
            data_provider: Instance or class of DataProvider
            priority: Optional priority for the data provider. If not
                provided, the data provider will be added with the default
                priority (3).

        Returns:
            None
        """
        if inspect.isclass(data_provider):
            if not issubclass(data_provider, DataProvider):
                raise OperationalException(
                    "Data provider should be an instance of DataProvider"
                )

            data_provider = data_provider()

        self._data_providers.append((data_provider, priority))

    def add_market_credential(
        self, market_credential: MarketCredential
    ) -> None:
        """
        Function to add a market credential to the app. The market
        credential should be an instance of MarketCredential.

        Args:
            market_credential:

        Returns:
            None
        """
        market_credential.market = market_credential.market.upper()
        market_credential_service = self.container \
            .market_credential_service()
        market_credential_service.add(market_credential)

    def on_initialize(self, app_hook):
        """
        Function to add a hook that runs when the app is initialized. The hook
        should be an instance of AppHook.

        Args:
            app_hook: Instance of AppHook

        Returns:
            None
        """

        # Check if the app_hook inherits from AppHook
        if not issubclass(app_hook, AppHook):
            raise OperationalException(
                "App hook should be an instance of AppHook"
            )

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_initialize_hooks.append(app_hook)

    def on_strategy_run(self, app_hook):
        """
        Function to add a hook that runs when a strategy is run. The hook
        should be an instance of AppHook.
        """

        # Check if the app_hook inherits from AppHook
        if inspect.isclass(app_hook) and not issubclass(app_hook, AppHook):
            raise OperationalException(
                "App hook should be an instance of AppHook"
            )

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_strategy_run_hooks.append(app_hook)

    def after_initialize(self, app_hook: AppHook):
        """
        Function to add a hook that runs after the app is initialized.
        The hook should be an instance of AppHook.
        """

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_after_initialize_hooks.append(app_hook)

    def strategy(
        self,
        function=None,
        schedule: Schedule = None,
        scheduled_functions: list = None,
        data_sources=None
    ):
        """
        Decorator for registering a strategy. This decorator can be used
        to define a trading strategy function and register it in your
        application.

        Args:
            function: The wrapped function to should be converted to
                a TradingStrategy
            schedule (Schedule): when to fire. Build with
                ``Schedule.every(interval, time_unit)`` or
                ``Schedule.on(date_rule, time_rule)``. Required in v9.0.
            scheduled_functions (List[ScheduledFunction]): optional list
                of additional hooks that fire on their own schedules
                (e.g. monthly rebalance).
            data_sources (List): List of data sources that the
                trading strategy function uses.

        Returns:
            Function
        """
        from .strategy import TradingStrategy

        if schedule is None:
            raise OperationalException(
                "@app.strategy requires a ``schedule=`` argument. Use "
                "``Schedule.every(interval, time_unit)`` or "
                "``Schedule.on(date_rule, time_rule)``. The legacy "
                "``time_unit=``/``interval=`` kwargs were removed in v9.0."
            )
        if not isinstance(schedule, Schedule):
            raise OperationalException(
                f"@app.strategy ``schedule=`` must be a Schedule "
                f"instance; got {type(schedule).__name__}."
            )

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                schedule=schedule,
                scheduled_functions=scheduled_functions,
                data_sources=data_sources
            )
            self.add_strategy(strategy_object)
            return strategy_object
        else:

            def wrapper(f):
                self.add_strategy(
                    TradingStrategy(
                        decorated=f,
                        schedule=schedule,
                        scheduled_functions=scheduled_functions,
                        data_sources=data_sources,
                    )
                )
                return f

            return wrapper

    def add_strategies(self, strategies, throw_exception=True) -> None:
        """
        Function to add strategies to the app
        Args:
            strategies (List(TradingStrategy)): List of trading strategies that
                need to be registered.
            throw_exception (boolean): Flag to specify if an exception
                can be thrown if the strategies are not in the format or type
                that the application expects

        Returns:
            None
        """

        if strategies is not None:
            for strategy in strategies:
                self.add_strategy(strategy, throw_exception=throw_exception)

    def add_strategy(self, strategy, throw_exception=True) -> None:
        """
        Function to add a strategy to the app. The strategy should be an
        instance of TradingStrategy or a subclass based on the TradingStrategy
        class.

        Args:
            strategy: Instance of TradingStrategy
            throw_exception: Flag to allow for throwing an exception when
                the provided strategy is not inline with what the application
                expects.

        Returns:
            None
        """

        logger.info("Adding strategy")

        if inspect.isclass(strategy):

            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            strategy = strategy()

        if not isinstance(strategy, TradingStrategy):

            if throw_exception:
                raise OperationalException(
                    "Strategy should be an instance of TradingStrategy"
                )
            else:
                return

        if not isinstance(strategy.schedule, Schedule):
            raise OperationalException(
                f"Schedule not set for strategy instance "
                f"{strategy.strategy_id}. Set ``schedule = "
                f"Schedule.every(...)`` or ``schedule = "
                f"Schedule.on(...)`` on the class, or pass "
                f"``schedule=`` to the constructor."
            )

        has_duplicates = False

        for existing_strategy in self._strategies:
            if existing_strategy.strategy_id == strategy.strategy_id:
                has_duplicates = True
                break

        if has_duplicates:
            raise OperationalException(
                "Can't add strategy, there already exists a strategy "
                "with the same id in the algorithm"
            )

        self._strategies.append(strategy)
        logger.info(f"Strategy added: {strategy.strategy_id}")

    def add_state_handler(self, state_handler):
        """
        Function to add a state handler to the app. The state handler should
        be an instance of StateHandler.

        Args:
            state_handler: Instance of StateHandler

        Returns:
            None
        """

        if inspect.isclass(state_handler):
            state_handler = state_handler()

        if not isinstance(state_handler, StateHandler):
            raise OperationalException(
                "State handler should be an instance of StateHandler"
            )

        self._state_handler = state_handler

    def add_market(
        self,
        market=None,
        trading_symbol=None,
        api_key=None,
        secret_key=None,
        initial_balance=None,
        fee_percentage=0.0,
        slippage_percentage=0.0,
        position_mode="netting",
        paper_trading=False,
        paper_trading_mode=PaperTradingMode.AUTO,
    ):
        """
        Function to add a market to the app. This function is a utility
        function to add a portfolio configuration and market credential
        to the app.

        Args:
            market: String representing the market name. Falls back to
                the ``MARKET`` environment variable when not given.
            trading_symbol: Trading symbol for the portfolio. Falls
                back to the ``TRADING_SYMBOL`` environment variable
                when not given.
            api_key: API key for the market
            secret_key: Secret key for the market
            initial_balance: Initial balance for the market. Falls
                back to the ``INITIAL_BALANCE`` environment variable
                when not given.
            fee_percentage: Default fee percentage for all trades
                on this market (e.g. 0.1 for 0.1%). Can be overridden
                per-symbol via TradingCost on the strategy.
            slippage_percentage: Default slippage percentage for all
                trades on this market (e.g. 0.05 for 0.05%). Can be
                overridden per-symbol via TradingCost on the strategy.
            position_mode: Position accounting mode. Defaults to NETTING;
                HEDGE stores independent long and short legs.
            paper_trading: When True, no real orders are ever placed
                for this market. See ``paper_trading_mode`` for how
                execution is simulated.
            paper_trading_mode: One of ``PaperTradingMode.AUTO``
                (default; prefers the broker's own sandbox/testnet,
                falls back to the local simulator),
                ``PaperTradingMode.BROKER`` (require the broker's
                sandbox; raises if unsupported), or
                ``PaperTradingMode.LOCAL`` (always simulate locally,
                no network calls to place orders).

        Returns:
            None
        """

        portfolio_configuration = PortfolioConfiguration(
            market=market,
            trading_symbol=trading_symbol,
            initial_balance=initial_balance,
            fee_percentage=fee_percentage,
            slippage_percentage=slippage_percentage,
            position_mode=position_mode,
            paper_trading=paper_trading,
            paper_trading_mode=paper_trading_mode,
        )
        self.add_portfolio_configuration(portfolio_configuration)

        use_broker_sandbox = False

        if portfolio_configuration.paper_trading:
            use_broker_sandbox = self._resolve_paper_trading_sandbox(
                portfolio_configuration
            )

        if portfolio_configuration.paper_trading and not use_broker_sandbox:
            # The local simulator never makes a network call, so it
            # doesn't need real credentials. Placeholder values satisfy
            # MarketCredentialService without requiring the user to
            # configure API keys for a market that will never place a
            # real order.
            api_key = api_key or "paper-trading"
            secret_key = secret_key or "paper-trading"

        market_credential = MarketCredential(
            market=portfolio_configuration.market,
            api_key=api_key,
            secret_key=secret_key
        )
        self.add_market_credential(market_credential)

        if portfolio_configuration.paper_trading:
            self._setup_paper_trading(
                portfolio_configuration, use_broker_sandbox
            )

    def _resolve_paper_trading_sandbox(
        self, portfolio_configuration: PortfolioConfiguration
    ) -> bool:
        """
        Determine whether paper trading for this market should use the
        broker's own sandbox/testnet, raising for
        ``PaperTradingMode.BROKER`` when it isn't available.
        """
        market = portfolio_configuration.market
        mode = portfolio_configuration.paper_trading_mode

        if mode == PaperTradingMode.LOCAL:
            return False

        supported = (
            CCXTOrderExecutor.supports_sandbox_mode(market)
            and CCXTPortfolioProvider.supports_sandbox_mode(market)
        )

        if mode == PaperTradingMode.BROKER and not supported:
            raise OperationalException(
                f"PaperTradingMode.BROKER was requested for market "
                f"{market}, but its exchange does not advertise a "
                f"sandbox/testnet endpoint. Use "
                f"PaperTradingMode.LOCAL or PaperTradingMode.AUTO "
                f"instead."
            )

        return supported

    def _setup_paper_trading(
        self,
        portfolio_configuration: PortfolioConfiguration,
        use_broker_sandbox: bool,
    ) -> None:
        """
        Register the order executor/portfolio provider pair for a
        paper-traded market, scoped to that market only so it never
        shadows a live market registered in the same app.
        """
        market = portfolio_configuration.market

        if use_broker_sandbox:
            logger.info(
                f"Paper trading for {market}: using the broker's own "
                f"sandbox/testnet"
            )
            self.add_order_executor(
                CCXTOrderExecutor(
                    priority=0, sandbox=True, markets=[market]
                )
            )
            self.add_portfolio_provider(
                CCXTPortfolioProvider(
                    priority=0, sandbox=True, markets=[market]
                )
            )
        else:
            logger.info(
                f"Paper trading for {market}: using the local, "
                f"broker-agnostic simulator"
            )
            self.add_order_executor(
                PaperTradingOrderExecutor(markets=[market], priority=0)
            )
            self.add_portfolio_provider(
                PaperTradingPortfolioProvider(markets=[market], priority=0)
            )

    def set_blotter(self, blotter):
        """
        Set a blotter for order book management. The blotter sits
        between the strategy and the order execution layer, enabling
        batch ordering, transaction tracking, and custom order routing.

        Args:
            blotter: Instance of Blotter

        Returns:
            None
        """

        if inspect.isclass(blotter):
            blotter = blotter()

        if not isinstance(blotter, Blotter):
            raise OperationalException(
                "Blotter should be an instance of Blotter"
            )

        self._blotter = blotter

    def get_blotter(self):
        """
        Get the configured blotter.

        Returns:
            Blotter or None: The configured blotter instance.
        """
        return self._blotter

    def set_base_currency(self, currency: str) -> None:
        """
        Set the base currency for multi-currency portfolio reporting.

        When a base currency is set and an FX rate provider is registered,
        the framework will automatically convert position values from
        their local currency to the base currency when computing
        portfolio totals.

        Args:
            currency: Currency code (e.g. "EUR", "USD", "GBP").

        Returns:
            None
        """
        self._base_currency = currency.upper()

    def get_base_currency(self) -> str:
        """
        Get the configured base currency.

        Returns:
            str or None: The base currency code, or None if not set.
        """
        return self._base_currency

    def add_fx_rate_provider(self, fx_rate_provider) -> None:
        """
        Register an FX rate provider for multi-currency portfolio
        support. The provider supplies exchange rates between
        currency pairs.

        Args:
            fx_rate_provider: Instance of FXRateProvider.

        Returns:
            None
        """
        from investing_algorithm_framework.domain.fx import FXRateProvider

        if inspect.isclass(fx_rate_provider):
            fx_rate_provider = fx_rate_provider()

        if not isinstance(fx_rate_provider, FXRateProvider):
            raise OperationalException(
                "FX rate provider should be an instance of FXRateProvider"
            )

        self._fx_rate_provider = fx_rate_provider

    def get_fx_rate_provider(self):
        """
        Get the configured FX rate provider.

        Returns:
            FXRateProvider or None: The FX rate provider instance.
        """
        return self._fx_rate_provider

    def add_order_executor(self, order_executor):
        """
        Function to add an order executor to the app. The order executor
        should be an instance of OrderExecutor.

        Args:
            order_executor: Instance of OrderExecutor

        Returns:
            None
        """

        if inspect.isclass(order_executor):
            order_executor = order_executor()

        if not isinstance(order_executor, OrderExecutor):
            raise OperationalException(
                "Order executor should be an instance of OrderExecutor"
            )

        order_executor_lookup = self.container.order_executor_lookup()
        order_executor_lookup.add_order_executor(
            order_executor=order_executor
        )

    def get_order_executors(self):
        """
        Function to get all order executors from the app. This method
        should be called when you want to get all order executors.

        Returns:
            List of OrderExecutor instances
        """
        order_executor_lookup = self.container.order_executor_lookup()
        return order_executor_lookup.get_all()

    def add_portfolio_provider(self, portfolio_provider):
        """
        Function to add a portfolio provider to the app. The portfolio
        provider should be an instance of PortfolioProvider.

        Args:
            portfolio_provider: Instance of PortfolioProvider

        Returns:
            None
        """

        if inspect.isclass(portfolio_provider):
            portfolio_provider = portfolio_provider()

        if not isinstance(portfolio_provider, PortfolioProvider):
            raise OperationalException(
                "Portfolio provider should be an instance of "
                "PortfolioProvider"
            )

        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        portfolio_provider_lookup.add_portfolio_provider(
            portfolio_provider=portfolio_provider
        )

    def get_portfolio_providers(self):
        """
        Function to get all portfolio providers from the app. This method
        should be called when you want to get all portfolio providers.

        Returns:
            List of PortfolioProvider instances
        """
        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        return portfolio_provider_lookup.get_all()

    def initialize_order_executors(self):
        """
        Function to initialize the order executors. This function will
        first check if the app is running in backtest mode or not. If it is
        running in backtest mode, all order executors will be removed
        (OrderBacktestService handles execution directly) and the
        SimulationBlotter will be set as the default blotter if no custom
        blotter has been configured.

        If it is not running in backtest mode, it will add the default
        CCXTOrderExecutor with a priority 3.
        """
        from investing_algorithm_framework.domain.blotter import \
            SimulationBlotter

        order_executor_lookup = self.container.order_executor_lookup()
        environment = self.config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            # In backtest mode, OrderBacktestService handles execution
            # directly — no order executor needed
            order_executor_lookup.reset()

            # Auto-set SimulationBlotter for backtesting if no
            # custom blotter has been configured
            if self._blotter is None:
                self._blotter = SimulationBlotter()
        else:
            portfolio_configuration_service = self.container \
                .portfolio_configuration_service()
            portfolio_configurations = \
                portfolio_configuration_service.get_all()
            has_live_market = any(
                not pc.paper_trading for pc in portfolio_configurations
            )

            # Skip the default CCXT executor entirely when every
            # configured market is paper-traded — it would never be
            # selected anyway (paper executors register at priority=0)
            # but still opens a real ccxt exchange client per market.
            if has_live_market or not portfolio_configurations:
                order_executor_lookup.add_order_executor(
                    CCXTOrderExecutor(priority=3)
                )

        for order_executor in order_executor_lookup.get_all():
            order_executor.config = self.config

        executors = ', '.join(
            f'{type(oe).__name__}(priority={oe.priority})'
            for oe in order_executor_lookup.get_all()
        ) or "none"
        logger.info(
            f"Order executors initialized "
            f"({len(order_executor_lookup.get_all())}): {executors}"
        )

    @staticmethod
    def _log_next_scheduled_runs(
        algorithm, run_immediately_on_start: bool = True
    ) -> None:
        """
        Log when each of the algorithm's strategies is next scheduled
        to run. Called once, right after portfolio syncing completes,
        so it's the last thing logged before the live loop starts.

        When ``run_immediately_on_start`` is True (default), the very
        first run always fires immediately once the live loop starts
        (there is no ``last_run`` yet), so this logs that plus the
        recurring interval for interval-based schedules. When False,
        the first run instead waits for the normal interval to elapse,
        so this logs that future time instead.
        """
        now = datetime.now(timezone.utc)
        formatted_now = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        for strategy in algorithm.strategies:
            schedule = strategy.schedule

            if schedule is None:
                continue

            if schedule.is_interval:
                unit = schedule.time_unit.value.lower()
                if run_immediately_on_start:
                    logger.info(
                        f"Strategy '{strategy.strategy_id}': runs every "
                        f"{schedule.interval} {unit}(s); first run at "
                        f"{formatted_now} (now)"
                    )
                else:
                    first_run = (now + schedule.step()).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                    logger.info(
                        f"Strategy '{strategy.strategy_id}': runs every "
                        f"{schedule.interval} {unit}(s); first run at "
                        f"{first_run}"
                    )
            else:
                logger.info(
                    f"Strategy '{strategy.strategy_id}': runs according "
                    "to its rule-based schedule; next run depends on "
                    "the configured date/time rules"
                )

    def initialize_portfolios(self):
        """
        Function to initialize the portfolios. This function will
        first check if the app is running in backtest mode or not. If it is
        running in backtest mode, it will create the portfolios with the
        initial amount specified in the config. If it is not running in
        backtest mode, it will check if there are

        """
        logger.info("Initializing portfolios")
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_service = self.container.portfolio_service()

        # Throw an error if no portfolios are configured
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        # Check if there are already existing portfolios
        portfolios = portfolio_service.get_all()
        portfolio_configurations = portfolio_configuration_service\
            .get_all()
        portfolio_provider_lookup = \
            self.container.portfolio_provider_lookup()

        if len(portfolios) > 0:

            # Check if there are matching portfolio configurations
            for portfolio in portfolios:
                logger.debug(
                    f"Checking if there is a matching portfolio "
                    f"configuration for portfolio {portfolio.identifier}"
                )
                portfolio_configuration = \
                    portfolio_configuration_service.get(
                        portfolio.market
                    )

                if portfolio_configuration is None:
                    raise ImproperlyConfigured(
                        f"No matching portfolio configuration found for "
                        f"existing portfolio {portfolio.market}, "
                        f"please make sure that you have configured your "
                        f"app with the right portfolio configurations "
                        f"for the existing portfolios."
                        f"If you want to create a new portfolio, please "
                        f"remove the existing database (WARNING!!: this "
                        f"will remove all existing history of your "
                        f"trading bot.)"
                    )

                # Check if the portfolio configuration is still inline
                # with the initial balance

                if portfolio_configuration.initial_balance != \
                        portfolio.initial_balance:
                    logger.warning(
                        "The initial balance of the portfolio "
                        "configuration is different from the existing "
                        "portfolio. Checking if the existing portfolio "
                        "can be updated..."
                    )

                    # Register a portfolio provider for the portfolio
                    portfolio_provider_lookup \
                        .register_portfolio_provider_for_market(
                            portfolio_configuration.market
                        )
                    initial_balance = portfolio_configuration\
                        .initial_balance

                    if initial_balance != portfolio.initial_balance:
                        raise ImproperlyConfigured(
                            "The initial balance of the portfolio "
                            "configuration is different then that of "
                            "the existing portfolio. Please make sure "
                            "that the initial balance of the portfolio "
                            "configuration is the same as that of the "
                            "existing portfolio. "
                            f"Existing portfolio initial balance: "
                            f"{portfolio.initial_balance}, "
                            f"Portfolio configuration initial balance: "
                            f"{portfolio_configuration.initial_balance}"
                            "If this is intentional, please remove "
                            "the database and re-run the app. "
                            "WARNING!!: this will remove all existing "
                            "history of your trading bot."
                        )

        order_executor_lookup = self.container.order_executor_lookup()
        market_credential_service = \
            self.container.market_credential_service()
        # Register portfolio providers and order executors
        for portfolio_configuration in portfolio_configurations:

            # Register a portfolio provider for the portfolio
            portfolio_provider_lookup\
                .register_portfolio_provider_for_market(
                    portfolio_configuration.market
                )

            # Register an order executor for the portfolio
            order_executor_lookup.register_order_executor_for_market(
                portfolio_configuration.market
            )

            market_credential = \
                market_credential_service.get(
                    portfolio_configuration.market
                )

            if market_credential is None:
                raise ImproperlyConfigured(
                    f"No market credential found for existing "
                    f"portfolio {portfolio_configuration.market} "
                    "with market "
                    "Cannot initialize portfolio configuration."
                )

            if not portfolio_service.exists(
                {"identifier": portfolio_configuration.identifier}
            ):
                portfolio_service.create_portfolio_from_configuration(
                    portfolio_configuration
                )

        portfolio_identifiers = ', '.join(
            p.identifier for p in portfolio_service.get_all()
        ) or "none"
        logger.info(
            f"Portfolios initialized "
            f"({len(portfolio_service.get_all())}): {portfolio_identifiers}"
        )
        portfolio_sync_service = self.container.portfolio_sync_service()

        for portfolio in portfolio_service.get_all():
            portfolio_sync_service.sync_unallocated(portfolio)
            portfolio_sync_service.sync_orders(portfolio)
            logger.info(f"Portfolio synced: {portfolio.identifier}")

    def initialize_backtest_portfolios(self):
        """
        Function to initialize the backtest portfolios. This function will
        create a default portfolio provider for each market that is configured
        in the app. The default portfolio provider will be used to create
        portfolios for the app.

        Returns:
            None
        """
        logger.info("Initializing backtest portfolios")
        config = self.config
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_service = self.container.portfolio_service()

        # Throw an error if no portfolios are configured
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        logger.info("Setting up backtest portfolios")
        initial_backtest_amount = config.get(
            BACKTESTING_INITIAL_AMOUNT, None
        )

        for portfolio_configuration \
                in portfolio_configuration_service.get_all():
            if not portfolio_service.exists(
                {"identifier": portfolio_configuration.identifier}
            ):
                portfolio_service.create_portfolio_from_configuration(
                    portfolio_configuration,
                    initial_amount=initial_backtest_amount,
                )

    def initialize_portfolio_providers(self):
        """
        Function to initialize the default portfolio providers.
        This function will create a default portfolio provider for
        each market that is configured in the app. The default portfolio
        provider will be used to create portfolios for the app.

        Returns:
            None
        """
        portfolio_provider_lookup = self.container\
            .portfolio_provider_lookup()
        environment = self.config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            # In backtest mode, remove all portfolio providers
            portfolio_provider_lookup.reset()
        else:
            portfolio_configuration_service = self.container \
                .portfolio_configuration_service()
            portfolio_configurations = \
                portfolio_configuration_service.get_all()
            has_live_market = any(
                not pc.paper_trading for pc in portfolio_configurations
            )

            # Skip the default CCXT provider entirely when every
            # configured market is paper-traded — see the matching
            # comment in initialize_order_executors().
            if has_live_market or not portfolio_configurations:
                portfolio_provider_lookup.add_portfolio_provider(
                    CCXTPortfolioProvider(priority=3)
                )

        for portfolio_provider in portfolio_provider_lookup.get_all():
            portfolio_provider.config = self.config

        providers = ', '.join(
            f'{type(pp).__name__}(priority={pp.priority})'
            for pp in portfolio_provider_lookup.get_all()
        ) or "none"
        logger.info(
            f"Portfolio providers initialized "
            f"({len(portfolio_provider_lookup.get_all())}): {providers}"
        )

    def get_run_history(self):
        """
        Function to get the run history of the app. This function will
        return the history of the run schedule of all the strategies,
        and tasks that have been registered in the app.

        Returns:
            dict: The run history of the app
        """
        return self._run_history

    def get_last_run_report(self) -> Optional[dict]:
        """
        Return a snapshot of what the most recent bounded ``run()``
        invocation did — the orders it created, every signal it
        evaluated (including ones rejected without an order), and the
        resulting positions, portfolios, and trades.

        Only populated after a non-web, bounded run (i.e. one where
        ``number_of_iterations`` was given, such as an AWS Lambda or
        Azure Function invocation) completes without raising. Intended
        to be returned directly as (or merged into) that invocation's
        response body.

        Returns:
            dict or None: The run report as a dict, or None if no
                bounded run has completed yet in this process.
        """
        if self._last_run_report is None:
            return None

        return self._last_run_report.to_dict()

    def get_run_reports(
        self, algorithm_id: str = None, limit: int = None
    ) -> List[dict]:
        """
        Return previously persisted run reports, most recent first.

        Unlike :py:meth:`get_last_run_report` (which only reflects the
        current process's most recent invocation), this reads from
        the database — so a stateless deployment (AWS Lambda, Azure
        Functions) can look back at prior invocations across separate
        processes.

        Args:
            algorithm_id (str): Optional algorithm id to filter by.
            limit (int): Optional maximum number of reports to return.

        Returns:
            List[dict]: Persisted run reports, most recently
                completed first.
        """
        query_params = {}

        if algorithm_id is not None:
            query_params["algorithm_id"] = algorithm_id

        reports = self.container.run_report_service().get_all(query_params)

        if limit is not None:
            reports = reports[:limit]

        return [report.to_dict() for report in reports]

    def _build_run_report(
        self,
        event_loop_service,
        run_started_at: datetime,
        algorithm=None,
        number_of_iterations: int = None,
    ) -> RunReport:
        """
        Assemble and persist a :class:`RunReport` for the run that
        just finished.

        Orders are filtered to those created *or updated* at or after
        ``run_started_at``, so an order placed in a previous run that
        only got filled (or otherwise changed status) in this one is
        still included — not just brand-new orders; positions,
        portfolios, and trades reflect current state (there are
        typically few enough of these live that a full snapshot is
        more useful than a diff). Each order/trade dict already
        carries its own ``strategy_id``, so a report covering several
        strategies can be attributed per-order.
        """
        order_service = self.container.order_service()
        trade_service = self.container.trade_service()
        position_service = self.container.position_service()
        portfolio_service = self.container.portfolio_service()
        run_report_service = self.container.run_report_service()

        def _aware(value):
            # SQLite round-trips can drop tzinfo; normalize to UTC so
            # naive/aware datetimes never fail to compare.
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        def _touched_this_run(order):
            created_at = _aware(order.created_at)
            updated_at = _aware(order.updated_at)
            return (
                created_at is not None and created_at >= run_started_at
            ) or (
                updated_at is not None and updated_at >= run_started_at
            )

        run_started_at = _aware(run_started_at)
        orders = [
            order.to_dict() for order in order_service.get_all()
            if _touched_this_run(order)
        ]
        positions = [
            position.to_dict() for position in position_service.get_all()
        ]
        portfolios = [
            portfolio.to_dict() for portfolio in portfolio_service.get_all()
        ]
        trades = [trade.to_dict() for trade in trade_service.get_all()]
        score_cards = [
            {
                "strategy_id": entry.get("strategy_id"),
                "symbol": item.get("symbol"),
                "summary": item.get("score_card", {}).get("summary"),
                "entries": item.get("score_card", {}).get("entries", []),
                "score_card_version": item.get("score_card", {}).get(
                    "score_card_version"
                ),
            }
            for entry in event_loop_service.signal_log
            for item in entry.get("score_cards", [])
        ]
        config = self.container.configuration_service().get_config()

        # A run is "paper" only when every configured portfolio is
        # paper-traded — a mixed live/paper setup is reported as not
        # paper, so real activity is never mistaken for fake trades.
        portfolio_configurations = self.container \
            .portfolio_configuration_service().get_all()
        is_paper = bool(portfolio_configurations) and all(
            pc.paper_trading for pc in portfolio_configurations
        )

        report = run_report_service.create({
            "algorithm_id": getattr(algorithm, "algorithm_id", None),
            "environment": config.get(ENVIRONMENT),
            "is_paper": is_paper,
            "number_of_iterations": number_of_iterations,
            "started_at": run_started_at,
            "completed_at": datetime.now(timezone.utc),
            "orders": orders,
            "signals": list(event_loop_service.signal_log),
            "positions": positions,
            "portfolios": portfolios,
            "trades": trades,
            "score_cards": score_cards,
        })
        return report

    def has_run(self, worker_id) -> bool:
        """
        Function to check if a worker has run in the app. This function
        will check if the worker_id is present in the run history of the app.

        Args:
            worker_id:

        Returns:
            Boolean: True if the worker has run, False otherwise
        """
        if self._run_history is None:
            return False

        return worker_id in self._run_history

    def get_algorithm(self):
        """
        Function to get the algorithm that is currently running in the app.
        This function will return the algorithm that is currently running
        in the app.

        Returns:
            Algorithm: The algorithm that is currently running in the app
        """
        algorithm_factory = self.container.algorithm_factory()
        return algorithm_factory.create_algorithm(
            strategies=self._strategies,
            tasks=self._tasks,
            on_strategy_run_hooks=self._on_strategy_run_hooks,
        )

    def cleanup_backtest_resources(self):
        """
        Clean up the backtest database and remove SQLAlchemy models/tables.
        """
        logger.info("Cleaning up backtest resources")
        config = self.config
        environment = config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            db_uri = config.get(SQLALCHEMY_DATABASE_URI)
            clear_db(db_uri)
