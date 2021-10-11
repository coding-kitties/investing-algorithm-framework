import logging

import sqlalchemy
from flask import Blueprint, request

from investing_algorithm_framework.configuration.constants import\
    SYMBOL_QUERY_PARAM, IDENTIFIER_QUERY_PARAM
from investing_algorithm_framework import Position, Portfolio, db
from investing_algorithm_framework.schemas import PositionSerializer
from investing_algorithm_framework.views.utils import normalize_query, \
    create_paginated_response

logger = logging.getLogger(__name__)

blueprint = Blueprint("position-views", __name__)


def apply_position_query_parameters(query_set):
    query_params = normalize_query(request.args)

    if SYMBOL_QUERY_PARAM in query_params:
        query_set = query_set.filter_by(
            symbol=query_params[SYMBOL_QUERY_PARAM]
        )

    if IDENTIFIER_QUERY_PARAM in query_params:
        portfolio = Portfolio.query\
            .filter_by(identifier=query_params[IDENTIFIER_QUERY_PARAM])\
            .first()

        if portfolio is None:
            return db.session.query(Position).filter(sqlalchemy.sql.false())

        query_set = query_set.filter_by(portfolio=portfolio)

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
