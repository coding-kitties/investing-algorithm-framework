from investing_algorithm_framework.app.web.controllers.orders import \
    blueprint as orders_blueprint
from investing_algorithm_framework.app.web.controllers.portfolio \
    import blueprint as portfolio_blueprint
from investing_algorithm_framework.app.web.controllers.positions import \
    blueprint as positions_blueprint
from investing_algorithm_framework.app.web.controllers.trades import \
    blueprint as trades_blueprint
from investing_algorithm_framework.app.web.controllers.algorithm import \
    blueprint as algorithm_blueprint
from investing_algorithm_framework.app.web.controllers.backtest_results \
    import blueprint as backtest_results_blueprint


def setup_blueprints(flask_app):
    flask_app.register_blueprint(portfolio_blueprint, prefix="/api")
    flask_app.register_blueprint(orders_blueprint, prefix="/api")
    flask_app.register_blueprint(positions_blueprint, prefix="/api")
    flask_app.register_blueprint(trades_blueprint, prefix="/api")
    flask_app.register_blueprint(algorithm_blueprint, prefix="/api")
    flask_app.register_blueprint(
        backtest_results_blueprint, prefix="/api"
    )
    return flask_app
