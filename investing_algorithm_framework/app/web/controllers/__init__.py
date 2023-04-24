from investing_algorithm_framework.app.web.controllers.portfolio \
    import blueprint as portfolio_blueprint
from investing_algorithm_framework.app.web.controllers.orders import \
    blueprint as orders_blueprint
from investing_algorithm_framework.app.web.controllers.positions import \
    blueprint as positions_blueprint


def setup_blueprints(flask_app):
    flask_app.register_blueprint(portfolio_blueprint, prefix="/api")
    flask_app.register_blueprint(orders_blueprint, prefix="/api")
    flask_app.register_blueprint(positions_blueprint, prefix="/api")
    return flask_app
