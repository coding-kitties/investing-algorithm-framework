import logging

from flask import Blueprint, request
from dependency_injector.wiring import inject, Provide
from investing_algorithm_framework.app.web.schemas import OrderSerializer
from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("order-views", __name__)


@blueprint.route("/api/orders", methods=["GET"])
@inject
def list_orders(order_service=Provide[DependencyContainer.order_service]):
    orders = order_service.get_all(request.args)
    return create_response(orders, OrderSerializer())
