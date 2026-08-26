import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import TradeSerializer
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

router = APIRouter()


@router.get("/api/trades")
@inject
def list_trades(
    request: Request,
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
):
    trades = trade_service.get_all(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(trades, TradeSerializer())


@router.get("/api/trades/count")
@inject
def count_trades(
    request: Request,
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
):
    """Return the count of trades matching the given filters."""
    count = trade_service.count(MultiDict(request.query_params.multi_items()))
    return JSONResponse(content={"count": count}, status_code=200)
