from investing_algorithm_framework import current_app
from .operational_views import blueprint as operational_views_blueprint
from investing_algorithm_framework.views.order_views import blueprint \
    as order_views_blueprint
from investing_algorithm_framework.views.position_views import blueprint \
    as position_views_blueprint
from investing_algorithm_framework.views.portfolio_views import blueprint \
    as portfolio_views_blueprint

app = current_app
app.register_blueprint(operational_views_blueprint)
app.register_blueprint(order_views_blueprint)
app.register_blueprint(position_views_blueprint)
app.register_blueprint(portfolio_views_blueprint)
