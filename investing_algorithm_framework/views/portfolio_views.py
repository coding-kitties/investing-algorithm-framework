import logging

from flask import Blueprint, jsonify

from investing_algorithm_framework import Portfolio
from investing_algorithm_framework.schemas import PortfolioSerializer
from investing_algorithm_framework.views.utils import create_paginated_response

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
def retrieve(identifier):
    """
    View for retrieving of an portfolio of the algorithm.
    """

    portfolio = Portfolio.query.filter_by(identifier=identifier)\
        .first_or_404("Portfolio not found")

    return jsonify(PortfolioSerializer().dump(portfolio)), 200
