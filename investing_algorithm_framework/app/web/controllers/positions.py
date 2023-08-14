import logging

from flask import Blueprint, request
from dependency_injector.wiring import inject, Provide

from investing_algorithm_framework.app.web.schemas import PositionSerializer
from investing_algorithm_framework.app.web.responses import create_response

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("position-views", __name__)


@blueprint.route("/api/positions", methods=["GET"])
@inject
def list_positions(position_service=Provide["position_service"]):
    positions = position_service.get_all(request.args)
    return create_response(positions, PositionSerializer())
