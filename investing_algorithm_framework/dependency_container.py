from dependency_injector import containers, providers

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.infrastructure import SQLOrderRepository, \
    SQLPositionRepository, MarketService, SQLPortfolioRepository, \
    SQLOrderFeeRepository, SQLPortfolioSnapshotRepository, \
    SQLPositionSnapshotRepository, PerformanceService
from investing_algorithm_framework.services import OrderService, \
    PositionService, PortfolioService, StrategyOrchestratorService, \
    PortfolioConfigurationService, MarketDataService, BackTestService, \
    ConfigurationService, PortfolioSnapshotService, PositionSnapshotService


def setup_dependency_container(app, modules=None, packages=None):
    app.container = DependencyContainer()
    app.container.wire(modules=modules, packages=packages)
    return app


class DependencyContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration()
    configuration_service = providers.ThreadSafeSingleton(
        ConfigurationService,
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
    market_service = providers.Factory(MarketService)
    market_data_service = providers.Factory(
        MarketDataService,
        market_service=market_service
    )
    portfolio_configuration_service = providers.ThreadSafeSingleton(
        PortfolioConfigurationService,
        market_service=market_service,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
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
    order_service = providers.Factory(
        OrderService,
        order_repository=order_repository,
        order_fee_repository=order_fee_repository,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
        market_service=market_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service
    )
    position_service = providers.Factory(
        PositionService,
        repository=position_repository,
        market_service=market_service,
        order_repository=order_repository,
    )
    portfolio_service = providers.Factory(
        PortfolioService,
        market_service=market_service,
        position_repository=position_repository,
        order_service=order_service,
        portfolio_repository=portfolio_repository,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_snapshot_service=portfolio_snapshot_service
    )
    strategy_orchestrator_service = providers.Factory(
        StrategyOrchestratorService,
        market_data_service=market_data_service
    )
    performance_service = providers.Factory(
        PerformanceService,
        order_repository=order_repository,
        position_repository=position_repository,
        portfolio_repository=portfolio_repository
    )
    backtest_service = providers.Factory(
        BackTestService,
        market_data_service=market_data_service,
        market_service=market_service,
        order_service=order_service,
        portfolio_repository=portfolio_repository,
        performance_service=performance_service,
        position_repository=position_repository,
    )
    algorithm = providers.Factory(
        Algorithm,
        configuration_service=configuration_service,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_service=portfolio_service,
        position_service=position_service,
        order_service=order_service,
        market_service=market_service,
        strategy_orchestrator_service=strategy_orchestrator_service,
        market_data_service=market_data_service,
    )

