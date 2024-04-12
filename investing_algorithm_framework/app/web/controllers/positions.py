import logging

from dependency_injector.wiring import inject, Provide
from flask import Blueprint, request

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import PositionSerializer

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("position-views", __name__)


@blueprint.route("/api/positions", methods=["GET"])
@inject
def list_positions(position_service=Provide["position_service"]):
    positions = position_service.get_all(request.args)
    return create_response(positions, PositionSerializer())
