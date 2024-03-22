from dependency_injector import containers, providers

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.infrastructure import SQLOrderRepository, \
    SQLPositionRepository, SQLPortfolioRepository, \
    SQLOrderFeeRepository, SQLPortfolioSnapshotRepository, \
    SQLPositionSnapshotRepository, PerformanceService, CCXTMarketService
from investing_algorithm_framework.services import OrderService, \
    PositionService, PortfolioService, StrategyOrchestratorService, \
    PortfolioConfigurationService, MarketDataSourceService, BacktestService, \
    ConfigurationService, PortfolioSnapshotService, PositionSnapshotService, \
    MarketCredentialService, TradeService, BacktestReportWriterService


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
    order_fee_repository = providers.Factory(SQLOrderFeeRepository)
    position_repository = providers.Factory(SQLPositionRepository)
    portfolio_repository = providers.Factory(SQLPortfolioRepository)
    position_snapshot_repository = providers.Factory(
        SQLPositionSnapshotRepository
    )
    portfolio_snapshot_repository = providers.Factory(
        SQLPortfolioSnapshotRepository
    )
    market_service = providers.Factory(
        CCXTMarketService,
        market_credential_service=market_credential_service,
    )
    market_data_source_service = providers.Factory(
        MarketDataSourceService,
        market_service=market_service,
        market_credential_service=market_credential_service,
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
    order_service = providers.Factory(
        OrderService,
        order_repository=order_repository,
        order_fee_repository=order_fee_repository,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
        market_service=market_service,
        market_credential_service=market_credential_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service
    )
    position_service = providers.Factory(
        PositionService,
        repository=position_repository,
        market_service=market_service,
        market_credential_service=market_credential_service,
        order_repository=order_repository,
    )
    portfolio_service = providers.Factory(
        PortfolioService,
        market_credential_service=market_credential_service,
        market_service=market_service,
        position_repository=position_repository,
        order_service=order_service,
        portfolio_repository=portfolio_repository,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service,
    )
    trade_service = providers.Factory(
        TradeService,
        portfolio_service=portfolio_service,
        order_service=order_service,
        market_data_source_service=market_data_source_service,
        position_service=position_service,
    )
    strategy_orchestrator_service = providers.Factory(
        StrategyOrchestratorService,
        market_data_source_service=market_data_source_service
    )
    performance_service = providers.Factory(
        PerformanceService,
        order_repository=order_repository,
        position_repository=position_repository,
        portfolio_repository=portfolio_repository
    )
    backtest_service = providers.Factory(
        BacktestService,
        order_service=order_service,
        portfolio_repository=portfolio_repository,
        performance_service=performance_service,
        position_repository=position_repository,
        market_data_source_service=market_data_source_service,
    )
    backtest_report_writer_service = providers.Factory(
        BacktestReportWriterService,
    )
    algorithm = providers.Factory(
        Algorithm,
        configuration_service=configuration_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_service=portfolio_service,
        position_service=position_service,
        order_service=order_service,
        strategy_orchestrator_service=strategy_orchestrator_service,
        market_credential_service=market_credential_service,
        market_data_source_service=market_data_source_service,
        market_service=market_service,
        trade_service=trade_service,
    )
