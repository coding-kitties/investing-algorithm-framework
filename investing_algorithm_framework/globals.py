import logging
from investing_algorithm_framework.app import App
from investing_algorithm_framework.core.models import TimeUnit
from investing_algorithm_framework.configuration.constants import \
    CHECK_PENDING_ORDERS

logger = logging.getLogger("investing-algorithm-framework")

current_app: App = App()


# Check pending orders every 5 minutes
@current_app.algorithm.schedule(
    worker_id="default_order_checker", time_unit=TimeUnit.MINUTE, interval=5
)
def check_pending_orders(context):

    if context.config.get(CHECK_PENDING_ORDERS, False):
        logger.info("Checking pending orders")
        context.check_pending_orders()
