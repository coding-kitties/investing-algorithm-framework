import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import \
    PortfolioSerializer, PortfolioOrderCostSerializer, \
    PortfolioOrderCostSpecificationSerializer
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


@router.get("/api/portfolios/order-costs")
@inject
def order_cost_overview(
    request: Request,
    portfolio_service=Depends(
        Provide[DependencyContainer.portfolio_service]
    ),
):
    """
    Return an overview of the order costs (fees and slippage) of the
    connected portfolios. Supports the same filters as `/api/portfolios`
    (e.g. `identifier`, `market`) to scope the overview to a single
    portfolio.
    """
    overview = portfolio_service.get_order_cost_overview(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(overview, PortfolioOrderCostSerializer())


@router.get("/api/portfolios/order-cost-specification")
@inject
def order_cost_specification(
    request: Request,
    portfolio_service=Depends(
        Provide[DependencyContainer.portfolio_service]
    ),
):
    """
    Return the order cost specification (the fee/slippage that would
    apply to a *new* order) of the connected portfolios — e.g. the fee
    percentage Bitvavo would charge for placing an order on that
    market. Supports the same filters as `/api/portfolios` (e.g.
    `identifier`, `market`) to scope to a single portfolio.
    """
    specification = portfolio_service.get_order_cost_specification(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(
        specification, PortfolioOrderCostSpecificationSerializer()
    )
