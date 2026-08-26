import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import PortfolioSerializer
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

router = APIRouter()


@router.get("/api/portfolios")
@inject
def retrieve(
    request: Request,
    portfolio_service=Depends(
        Provide[DependencyContainer.portfolio_service]
    ),
):
    portfolios = portfolio_service.get_all(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(portfolios, PortfolioSerializer())
