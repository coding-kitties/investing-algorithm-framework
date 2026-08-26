from investing_algorithm_framework.app.web.controllers.orders import \
    router as orders_router
from investing_algorithm_framework.app.web.controllers.portfolio \
    import router as portfolio_router
from investing_algorithm_framework.app.web.controllers.positions import \
    router as positions_router
from investing_algorithm_framework.app.web.controllers.trades import \
    router as trades_router
from investing_algorithm_framework.app.web.controllers.algorithm import \
    router as algorithm_router
from investing_algorithm_framework.app.web.controllers.backtest_results \
    import router as backtest_results_router
from investing_algorithm_framework.app.web.controllers.run_reports \
    import router as run_reports_router


def setup_routers(fastapi_app):
    fastapi_app.include_router(portfolio_router)
    fastapi_app.include_router(orders_router)
    fastapi_app.include_router(positions_router)
    fastapi_app.include_router(trades_router)
    fastapi_app.include_router(algorithm_router)
    fastapi_app.include_router(backtest_results_router)
    fastapi_app.include_router(run_reports_router)
    return fastapi_app
