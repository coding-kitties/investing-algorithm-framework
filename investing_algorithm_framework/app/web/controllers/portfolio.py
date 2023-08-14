import logging

from dependency_injector.wiring import inject, Provide
from flask import Blueprint, request

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import PortfolioSerializer
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("portfolio-views", __name__)


@blueprint.route("/api/portfolios", methods=["GET"])
@inject
def retrieve(portfolio_service=Provide[DependencyContainer.portfolio_service]):
    portfolios = portfolio_service.get_all(request.args)
    return create_response(portfolios, PortfolioSerializer())
