import logging

from flask import Blueprint, request

from investing_algorithm_framework import Order, Position, \
    Portfolio, OrderSide
from investing_algorithm_framework.schemas import OrderSerializer
from investing_algorithm_framework.views.utils import normalize_query, \
    create_paginated_response

logger = logging.getLogger(__name__)

blueprint = Blueprint("order-views", __name__)

TARGET_SYMBOL_QUERY_PARAM = "target_symbol"
TRADING_SYMBOL_QUERY_PARAM = "trading_symbol"
ORDER_SIDE_QUERY_PARAM = "order_side"
PENDING = "pending"


def apply_order_query_parameters(query_set):
    query_params = normalize_query(request.args)

    if TARGET_SYMBOL_QUERY_PARAM in query_params:
        query_set = query_set.filter_by(
            target_symbol=query_params[TARGET_SYMBOL_QUERY_PARAM]
        )

    if TRADING_SYMBOL_QUERY_PARAM in query_params:
        query_set = query_set.filter_by(
            trading_symbol=query_params[TRADING_SYMBOL_QUERY_PARAM]
        )

    if ORDER_SIDE_QUERY_PARAM in query_params:
        query_set = query_set.filter_by(
            order_side=OrderSide.from_string(
                query_params[ORDER_SIDE_QUERY_PARAM]
            ).value
        )

    if PENDING in query_params:
        query_set = query_set.filter_by(executed=query_params[PENDING])

    return query_set


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

    # Query orders
    query_set = apply_order_query_parameters(Order.query)

    # Create serializer
    serializer = OrderSerializer()

    # Paginate query
    return create_paginated_response(query_set, serializer), 200


@blueprint.route("/api/orders/positions/<int:position_id>", methods=["GET"])
def list_orders_of_position(position_id):
    query_set = Order.query.filter_by(position_id=position_id)
    query_set = apply_order_query_parameters(query_set)

    # Create serializer
    serializer = OrderSerializer(exclude=["position_id"])

    # Paginate query
    return create_paginated_response(query_set, serializer), 200


@blueprint.route("/api/orders/identifiers/<string:identifier>", methods=["GET"])
def list_orders_of_broker(identifier):
    portfolio = Portfolio.query.filter_by(identifier=identifier).first_or_404(
        f"Portfolio not found for given identifier {identifier}"
    )

    # Retrieve positions
    positions = Position.query\
        .filter_by(portfolio=portfolio)\
        .with_entities(Position.id)

    query_set = Order.query.filter(Order.position_id.in_(positions))
    query_set = apply_order_query_parameters(query_set)

    # Create serializer
    serializer = OrderSerializer(exclude=["identifier"])

    # Paginate query
    return create_paginated_response(query_set, serializer), 200
