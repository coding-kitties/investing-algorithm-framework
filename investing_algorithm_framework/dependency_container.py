from dependency_injector import containers, providers

from investing_algorithm_framework.app.context import Context
from investing_algorithm_framework.app.algorithm import AlgorithmFactory
from investing_algorithm_framework.infrastructure import SQLOrderRepository, \
    SQLPositionRepository, SQLPortfolioRepository, \
    SQLPortfolioSnapshotRepository, SQLTradeRepository, \
    SQLPositionSnapshotRepository, PerformanceService, CCXTMarketService, \
    SQLTradeStopLossRepository, SQLTradeTakeProfitRepository, \
    SQLOrderMetadataRepository
from investing_algorithm_framework.services import OrderService, \
    PositionService, PortfolioService, StrategyOrchestratorService, \
    PortfolioConfigurationService, MarketDataSourceService, BacktestService, \
    ConfigurationService, PortfolioSnapshotService, PositionSnapshotService, \
    MarketCredentialService, TradeService, PortfolioSyncService, \
    OrderExecutorLookup, PortfolioProviderLookup


def setup_dependency_container(app, modules=None, packages=None):
    app.container = DependencyContainer()
    app.container.wire(modules=modules, packages=packages)
    return app


class DependencyContainer(containers.DeclarativeContainer):
    """
    Dependency container for the app. It is responsible for managing the
    dependencies of the app.
    """
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration()
    configuration_service = providers.ThreadSafeSingleton(
        ConfigurationService,
    )
    market_credential_service = providers.ThreadSafeSingleton(
        MarketCredentialService
    )
    order_repository = providers.Factory(SQLOrderRepository)
    order_executor_lookup = providers.ThreadSafeSingleton(
        OrderExecutorLookup
    )
    order_metadata_repository = providers.Factory(SQLOrderMetadataRepository)
    position_repository = providers.Factory(SQLPositionRepository)
    portfolio_provider_lookup = providers.ThreadSafeSingleton(
        PortfolioProviderLookup,
    )
    portfolio_repository = providers.Factory(SQLPortfolioRepository)
    position_snapshot_repository = providers.Factory(
        SQLPositionSnapshotRepository
    )
    portfolio_snapshot_repository = providers.Factory(
        SQLPortfolioSnapshotRepository
    )
    trade_repository = providers.Factory(SQLTradeRepository)
    trade_take_profit_repository = providers\
        .Factory(SQLTradeTakeProfitRepository)
    trade_stop_loss_repository = providers.Factory(SQLTradeStopLossRepository)
    market_service = providers.Factory(
        CCXTMarketService,
        market_credential_service=market_credential_service,
    )
    market_data_source_service = providers.ThreadSafeSingleton(
        MarketDataSourceService,
        market_service=market_service,
        market_credential_service=market_credential_service,
        configuration_service=configuration_service
    )
    position_snapshot_service = providers.Factory(
        PositionSnapshotService,
        repository=position_snapshot_repository,
    )
    portfolio_snapshot_service = providers.Factory(
        PortfolioSnapshotService,
        repository=portfolio_snapshot_repository,
        position_snapshot_service=position_snapshot_service,
        position_repository=position_repository,
    )
    portfolio_configuration_service = providers.ThreadSafeSingleton(
        PortfolioConfigurationService,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
    )
    trade_service = providers.Factory(
        TradeService,
        order_repository=order_repository,
        trade_take_profit_repository=trade_take_profit_repository,
        trade_stop_loss_repository=trade_stop_loss_repository,
        configuration_service=configuration_service,
        trade_repository=trade_repository,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
        market_data_source_service=market_data_source_service,
        order_metadata_repository=order_metadata_repository,
    )
    position_service = providers.Factory(
        PositionService,
        portfolio_repository=portfolio_repository,
        repository=position_repository,
    )
    order_service = providers.Factory(
        OrderService,
        configuration_service=configuration_service,
        order_repository=order_repository,
        portfolio_repository=portfolio_repository,
        position_service=position_service,
        market_credential_service=market_credential_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service,
        trade_service=trade_service,
        order_executor_lookup=order_executor_lookup,
        portfolio_provider_lookup=portfolio_provider_lookup
    )
    portfolio_service = providers.Factory(
        PortfolioService,
        configuration_service=configuration_service,
        market_credential_service=market_credential_service,
        order_service=order_service,
        position_service=position_service,
        portfolio_repository=portfolio_repository,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service,
        portfolio_provider_lookup=portfolio_provider_lookup
    )
    portfolio_sync_service = providers.Factory(
        PortfolioSyncService,
        trade_service=trade_service,
        configuration_service=configuration_service,
        order_service=order_service,
        position_repository=position_repository,
        portfolio_repository=portfolio_repository,
        portfolio_configuration_service=portfolio_configuration_service,
        market_credential_service=market_credential_service,
        market_service=market_service,
        portfolio_provider_lookup=portfolio_provider_lookup,
    )
    strategy_orchestrator_service = providers.Factory(
        StrategyOrchestratorService,
        market_data_source_service=market_data_source_service,
        configuration_service=configuration_service,
    )
    performance_service = providers.Factory(
        PerformanceService,
        trade_repository=trade_repository,
        order_repository=order_repository,
        position_repository=position_repository,
        portfolio_repository=portfolio_repository
    )
    backtest_service = providers.Factory(
        BacktestService,
        configuration_service=configuration_service,
        order_service=order_service,
        portfolio_service=portfolio_service,
        performance_service=performance_service,
        position_repository=position_repository,
        market_data_source_service=market_data_source_service,
        portfolio_configuration_service=portfolio_configuration_service,
        strategy_orchestrator_service=strategy_orchestrator_service,
        portfolio_snapshot_service=portfolio_snapshot_service,
    )
    context = providers.Factory(
        Context,
        configuration_service=configuration_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_service=portfolio_service,
        position_service=position_service,
        order_service=order_service,
        market_credential_service=market_credential_service,
        market_data_source_service=market_data_source_service,
        market_service=market_service,
        trade_service=trade_service,
    )
    algorithm_factory = providers.Factory(
        AlgorithmFactory,
    )
