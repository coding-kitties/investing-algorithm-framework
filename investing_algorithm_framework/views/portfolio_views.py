import logging

from flask import Blueprint, jsonify, request

from investing_algorithm_framework import Portfolio, current_app
from investing_algorithm_framework.schemas import PortfolioSerializer
from investing_algorithm_framework.views.utils import \
    create_paginated_response, get_query_param
from investing_algorithm_framework.core.models import TimeFrame
from investing_algorithm_framework.configuration.constants \
    import TIME_FRAME_QUERY_PARAM

logger = logging.getLogger(__name__)

blueprint = Blueprint("portfolio-views", __name__)


@blueprint.route("/api/portfolios", methods=["GET"])
def list_portfolios():
    """
    View for listing of the portfolios of the algorithm. This view will list
    all the portfolios of of your algorithm.

    The response in the view is paginated.
    """
    # Paginate query
    return create_paginated_response(
        Portfolio.query, PortfolioSerializer()
    ), 200


@blueprint.route("/api/portfolios/<string:identifier>", methods=["GET"])
def retrieve(identifier="default"):
    """
    View for retrieving of an portfolio of the algorithm.
    """

    # Get the default portfolio
    if identifier == "default":
        portfolio = current_app.algorithm\
            .get_portfolio_manager()\
            .get_portfolio()
    else:
        portfolio = Portfolio.query.filter_by(identifier=identifier)\
            .first_or_404("Portfolio not found")

    time_frame = get_query_param(
        TIME_FRAME_QUERY_PARAM, request.args, TimeFrame.ONE_DAY.value
    )

    return jsonify(
        PortfolioSerializer(context={"time_frame": time_frame})
        .dump(portfolio)
    ), 200
