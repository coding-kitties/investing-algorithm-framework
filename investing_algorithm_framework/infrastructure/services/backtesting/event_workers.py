"""Spawn workers with private event-engine services and SQLite databases."""

from copy import deepcopy
from tempfile import TemporaryDirectory

from investing_algorithm_framework.domain import (
    BACKTESTING_INITIAL_AMOUNT, DATABASE_DIRECTORY_PATH, DATABASE_NAME,
    RESOURCE_DIRECTORY, SNAPSHOT_INTERVAL, SQLALCHEMY_DATABASE_URI,
)


_data_provider_index = None
_settings = None


def initialize_event_worker(data_provider_index, settings):
    global _data_provider_index, _settings
    _data_provider_index = data_provider_index
    _settings = settings


def run_event_worker(arguments):
    from investing_algorithm_framework import create_app
    from investing_algorithm_framework.infrastructure.database.sql_alchemy \
        import teardown_sqlalchemy

    algorithm, date_range = arguments
    settings = _settings
    with TemporaryDirectory(prefix="iaf-event-worker-") as directory:
        config = deepcopy(settings["config"])
        for key in (
            DATABASE_DIRECTORY_PATH, DATABASE_NAME, SQLALCHEMY_DATABASE_URI,
        ):
            config.pop(key, None)
        config[RESOURCE_DIRECTORY] = directory
        app = create_app(config=config)
        try:
            app.initialize_backtest_config(
                backtest_date_range=date_range,
                snapshot_interval=config.get(SNAPSHOT_INTERVAL),
                initial_amount=config[BACKTESTING_INITIAL_AMOUNT],
            )
            app.initialize_storage(remove_database_if_exists=False)
            if settings["blotter"] is not None:
                app.set_blotter(deepcopy(settings["blotter"]))
            app.initialize_backtest_services()
            for portfolio in deepcopy(settings["portfolios"]):
                app.add_portfolio_configuration(portfolio)
            app.initialize_backtest_portfolios()

            # Reuse the prepared window data without inheriting the parent's
            # service container, connections, or mutable portfolio state.
            data_service = app.container.data_provider_service()
            data_service.data_provider_index = _data_provider_index
            data_service.backtest_mode = True
            results = app.container.backtest_service().run_backtests(
                algorithms=[algorithm],
                context=app.context,
                trade_stop_loss_service=(
                    app.container.trade_stop_loss_service()
                ),
                trade_take_profit_service=(
                    app.container.trade_take_profit_service()
                ),
                backtest_date_range=date_range,
                risk_free_rate=settings["risk_free_rate"],
                skip_data_sources_initialization=True,
                continue_on_error=settings["continue_on_error"],
                blotter=app.get_blotter(),
                memory_budget_mb=settings["memory_budget_mb"],
                min_available_memory_mb=settings["min_available_memory_mb"],
            )
            # Only the coordinator merges bundles and writes checkpoints.
            return results
        finally:
            teardown_sqlalchemy()
            app.container.unwire()
            app.container.reset_singletons()
