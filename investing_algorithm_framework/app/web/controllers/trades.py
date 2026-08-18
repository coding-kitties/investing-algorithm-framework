import logging

from dependency_injector.wiring import inject, Provide
from flask import Blueprint, jsonify, request

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas import TradeSerializer
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("trade-views", __name__)


@blueprint.route("/api/trades", methods=["GET"])
@inject
def list_trades(trade_service=Provide[DependencyContainer.trade_service]):
    trades = trade_service.get_all(request.args)
    return create_response(trades, TradeSerializer())


@blueprint.route("/api/trades/count", methods=["GET"])
@inject
def count_trades(trade_service=Provide[DependencyContainer.trade_service]):
    """Return the count of trades matching the given filters."""
    count = trade_service.count(request.args)
    return jsonify({"count": count}), 200
