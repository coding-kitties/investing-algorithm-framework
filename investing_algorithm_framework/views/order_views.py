import logging

import sqlalchemy
from flask import Blueprint, request

from investing_algorithm_framework import current_app
from investing_algorithm_framework import Order, Position, \
    Portfolio, OrderSide, db
from investing_algorithm_framework.configuration.constants import \
    TARGET_SYMBOL_QUERY_PARAM, TRADING_SYMBOL_QUERY_PARAM, \
    IDENTIFIER_QUERY_PARAM, ORDER_SIDE_QUERY_PARAM, STATUS_QUERY_PARAM, \
    POSITION_SYMBOL_QUERY_PARAM
from investing_algorithm_framework.schemas import OrderSerializer
from investing_algorithm_framework.views.utils import normalize_query, \
    create_paginated_response, get_query_param
from investing_algorithm_framework import OperationalException, ApiException

logger = logging.getLogger(__name__)

blueprint = Blueprint("order-views", __name__)


def apply_order_query_parameters(query_set):
    query_params = normalize_query(request.args)

    if IDENTIFIER_QUERY_PARAM in query_params:
        portfolio = Portfolio.query\
            .filter_by(identifier=query_params[IDENTIFIER_QUERY_PARAM])\
            .first()

        if portfolio is None:
            return db.session.query(Order).filter(sqlalchemy.sql.false())

        position_ids = portfolio.positions.with_entities(Position.id)
        query_set = query_set.filter(Order.position_id.in_(position_ids))

    if POSITION_SYMBOL_QUERY_PARAM in query_params:
        position_ids = Position.query\
            .filter_by(symbol=query_params[POSITION_SYMBOL_QUERY_PARAM])\
            .with_entities(Position.id)

        query_set = query_set.filter(Order.position_id.in_(position_ids))

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

    if STATUS_QUERY_PARAM in query_params:
        query_set = query_set\
            .filter_by(status=query_params[STATUS_QUERY_PARAM])

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

    try:
        identifier = get_query_param(IDENTIFIER_QUERY_PARAM, request.args)
        portfolio = current_app.algorithm.get_portfolio(identifier)
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
