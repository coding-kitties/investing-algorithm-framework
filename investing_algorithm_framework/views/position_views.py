import logging

from flask import Blueprint, request

from investing_algorithm_framework import Position, Portfolio
from investing_algorithm_framework.schemas import PositionSerializer
from investing_algorithm_framework.views.utils import normalize_query, \
    create_paginated_response

logger = logging.getLogger(__name__)

blueprint = Blueprint("position-views", __name__)

SYMBOL_QUERY_PARAM = "symbol"


def apply_position_query_parameters(query_set):
    query_params = normalize_query(request.args)

    if SYMBOL_QUERY_PARAM in query_params:
        query_set = query_set.filter_by(
            symbol=query_params[SYMBOL_QUERY_PARAM]
        )

    return query_set


@blueprint.route("/api/positions", methods=["GET"])
def list_positions():
    """
    View for listing of the positions of the algorithm. This view will list all
    the positions of all portfolios of your algorithm.

    You can provide to this view the following query params:
        - symbol: the symbol that is traded in the orders that belong to the
        position.
    The response in the view is paginated.
    """

    # Query positions
    query_set = apply_position_query_parameters(Position.query)

    # Create serializer
    serializer = PositionSerializer()

    # Paginate query
    return create_paginated_response(query_set, serializer), 200


@blueprint.route("/api/positions/brokers/<string:broker_name>", methods=["GET"])
def list_positions_of_broker(broker_name):
    """
    View for listing of the positions of an broker. This view will list all
    the positions corresponding to the given broker/portfolio.

    You can provide to this view the following query params:
        - symbol: the symbol that is traded in the orders that belong to the
        position.
    The response in the view is paginated.
    """

    portfolio = Portfolio.query.filter_by(broker=broker_name).first_or_404(
        f"Portfolio not found for given broker {broker_name}"
    )

    # Retrieve positions
    query_set = apply_position_query_parameters(
        Position.query.filter_by(portfolio=portfolio)
    )

    # Create serializer
    serializer = PositionSerializer(exclude=["broker"])

    # Paginate query
    return create_paginated_response(query_set, serializer), 200
