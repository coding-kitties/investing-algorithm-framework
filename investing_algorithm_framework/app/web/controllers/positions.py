import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import PositionSerializer

logger = logging.getLogger("investing_algorithm_framework")

router = APIRouter()


@router.get("/api/positions")
@inject
def list_positions(
    request: Request,
    position_service=Depends(Provide["position_service"]),
):
    positions = position_service.get_all(
        MultiDict(request.query_params.multi_items())
    )
    return create_response(positions, PositionSerializer())
