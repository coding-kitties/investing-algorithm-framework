from dependency_injector import containers, providers

from investing_algorithm_framework.infrastructure import SQLOrderRepository, \
    SQLPositionRepository, MarketService, SQLPortfolioRepository
from investing_algorithm_framework.services import OrderService, \
    PositionService, PortfolioService, StrategyOrchestratorService, \
    PortfolioConfigurationService, MarketDataService
from investing_algorithm_framework.app.algorithm import Algorithm


def setup_dependency_container(app, modules=None, packages=None):
    app.container = DependencyContainer()
    app.container.wire(modules=modules, packages=packages)
    return app


class DependencyContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration()
    order_repository = providers.Factory(SQLOrderRepository)
    position_repository = providers.Factory(SQLPositionRepository)
    portfolio_repository = providers.Factory(SQLPortfolioRepository)
    market_service = providers.Factory(MarketService)
    market_data_service = providers.Factory(
        MarketDataService,
        market_service=market_service
    )
    portfolio_configuration_service = providers.Singleton(
        PortfolioConfigurationService,
        market_service=market_service,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
    )
    order_service = providers.Factory(
        OrderService,
        order_repository=order_repository,
        portfolio_repository=portfolio_repository,
        position_repository=position_repository,
        market_service=market_service,
        portfolio_configuration_service=portfolio_configuration_service,
    )
    position_service = providers.Factory(
        PositionService,
        repository=position_repository,
        market_service=market_service,
    )
    portfolio_service = providers.Factory(
        PortfolioService,
        market_service=market_service,
        position_repository=position_repository,
        order_repository=order_repository,
        portfolio_repository=portfolio_repository,
        portfolio_configuration_service=portfolio_configuration_service
    )
    strategy_orchestrator_service = providers.Factory(
        StrategyOrchestratorService,
        market_data_service=market_data_service
    )
    algorithm = providers.Factory(
        Algorithm,
        portfolio_configuration_service=portfolio_configuration_service,
        portfolio_service=portfolio_service,
        position_service=position_service,
        order_service=order_service,
        market_service=market_service,
        strategy_orchestrator_service=strategy_orchestrator_service,
        market_data_service=market_data_service
    )
