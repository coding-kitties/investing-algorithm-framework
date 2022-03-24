import logging

from flask import Blueprint, request

from investing_algorithm_framework import current_app, OperationalException, \
    ApiException
from investing_algorithm_framework.configuration.constants import \
    IDENTIFIER_QUERY_PARAM
from investing_algorithm_framework.schemas import PositionSerializer
from investing_algorithm_framework.views.utils import \
    create_paginated_response, get_query_param

logger = logging.getLogger(__name__)

blueprint = Blueprint("position-views", __name__)


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
    try:

        identifier = get_query_param(
            IDENTIFIER_QUERY_PARAM, request.args, None
        )
        positions = current_app.algorithm.get_positions(identifier=identifier)
    except OperationalException as e:
        raise ApiException(e.error_message, status_code=404)

    return create_paginated_response(positions, PositionSerializer()), 200
