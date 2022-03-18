import logging

from flask import Blueprint, request

from investing_algorithm_framework import OperationalException, ApiException
from investing_algorithm_framework import current_app
from investing_algorithm_framework.configuration.constants import \
    TARGET_SYMBOL_QUERY_PARAM, IDENTIFIER_QUERY_PARAM, ORDER_SIDE_QUERY_PARAM, \
    STATUS_QUERY_PARAM
from investing_algorithm_framework.schemas import OrderSerializer
from investing_algorithm_framework.views.utils import \
    create_paginated_response, get_query_param

logger = logging.getLogger(__name__)

blueprint = Blueprint("order-views", __name__)


@blueprint.route("/api/orders", methods=["GET"])
def list_orders():
    """
    View for listing of the orders of the algorithm. This view will list all
    the orders of all portfolios of your algorithm.

    You can provide to this view the following query params:
        - target_symbol: the symbol that is traded in the order.
        - trading_symbol: the symbol that is traded with in the order
        - order_side: the order side of the order (BUY/SELL)

    The response in the view is paginated.
    """

    try:
        identifier = get_query_param(IDENTIFIER_QUERY_PARAM, request.args)
        portfolio = current_app.algorithm.get_portfolio(identifier)

        # Query params
        status = get_query_param(STATUS_QUERY_PARAM, request.args)
        symbol = get_query_param(TARGET_SYMBOL_QUERY_PARAM, request.args)
        side = get_query_param(ORDER_SIDE_QUERY_PARAM, request.args)

        orders = portfolio\
            .get_orders(
                status=status,
                side=side,
                target_symbol=symbol
            )

        # Create serializer
        serializer = OrderSerializer()
    except OperationalException as e:
        raise ApiException(e.error_message)

    # Paginate query
    return create_paginated_response(
        orders,
        serializer,
        get_query_param("page", request.args, 1),
        get_query_param("per_page", request.args, 20)
    ), 200
