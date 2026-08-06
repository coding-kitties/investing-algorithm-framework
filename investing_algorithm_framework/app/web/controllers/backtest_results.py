import logging

from dependency_injector.wiring import inject, Provide
from flask import Blueprint, request

from investing_algorithm_framework.app.web.responses import create_response
from investing_algorithm_framework.app.web.schemas.backtest_result import (
    BacktestRunOrderSerializer,
    BacktestRunTradeSerializer,
    BacktestRunPositionSerializer,
    PortfolioSnapshotSerializer,
)
from investing_algorithm_framework.dependency_container import \
    DependencyContainer

logger = logging.getLogger("investing_algorithm_framework")

blueprint = Blueprint("backtest-result-views", __name__)


@blueprint.route("/api/backtest-results/orders", methods=["GET"])
@inject
def list_backtest_orders(
    order_service=Provide[DependencyContainer.order_service],
):
    """List all orders from the current backtest run.

    Supports the same query-parameter filters as ``/api/orders``
    (e.g. ``?status=CLOSED&portfolio=default``).
    """
    orders = order_service.get_all(request.args)
    return create_response(orders, BacktestRunOrderSerializer())


@blueprint.route("/api/backtest-results/orders/count", methods=["GET"])
@inject
def count_backtest_orders(
    order_service=Provide[DependencyContainer.order_service],
):
    """Return the count of orders matching the given filters."""
    from flask import jsonify
    count = order_service.count(request.args)
    return jsonify({"count": count}), 200


@blueprint.route("/api/backtest-results/trades", methods=["GET"])
@inject
def list_backtest_trades(
    trade_service=Provide[DependencyContainer.trade_service],
):
    """List all trades from the current backtest run."""
    trades = trade_service.get_all(request.args)
    return create_response(trades, BacktestRunTradeSerializer())


@blueprint.route("/api/backtest-results/trades/count", methods=["GET"])
@inject
def count_backtest_trades(
    trade_service=Provide[DependencyContainer.trade_service],
):
    """Return the count of trades matching the given filters."""
    from flask import jsonify
    count = trade_service.count(request.args)
    return jsonify({"count": count}), 200


@blueprint.route("/api/backtest-results/positions", methods=["GET"])
@inject
def list_backtest_positions(
    position_service=Provide[DependencyContainer.position_service],
):
    """List all positions from the current backtest run."""
    positions = position_service.get_all(request.args)
    return create_response(positions, BacktestRunPositionSerializer())


@blueprint.route("/api/backtest-results/positions/count", methods=["GET"])
@inject
def count_backtest_positions(
    position_service=Provide[DependencyContainer.position_service],
):
    """Return the count of positions matching the given filters."""
    from flask import jsonify
    count = position_service.count(request.args)
    return jsonify({"count": count}), 200


@blueprint.route("/api/backtest-results/portfolio-snapshots", methods=["GET"])
@inject
def list_backtest_portfolio_snapshots(
    portfolio_snapshot_service=Provide[
        DependencyContainer.portfolio_snapshot_service
    ],
):
    """List all portfolio snapshots from the current backtest run."""
    snapshots = portfolio_snapshot_service.get_all(request.args)
    return create_response(snapshots, PortfolioSnapshotSerializer())


@blueprint.route(
    "/api/backtest-results/portfolio-snapshots/count", methods=["GET"]
)
@inject
def count_backtest_portfolio_snapshots(
    portfolio_snapshot_service=Provide[
        DependencyContainer.portfolio_snapshot_service
    ],
):
    """Return the count of portfolio snapshots matching the given filters."""
    from flask import jsonify
    count = portfolio_snapshot_service.count(request.args)
    return jsonify({"count": count}), 200


@blueprint.route("/api/backtest-results/metrics", methods=["GET"])
@inject
def get_backtest_metrics(
    order_service=Provide[DependencyContainer.order_service],
    trade_service=Provide[DependencyContainer.trade_service],
    position_service=Provide[DependencyContainer.position_service],
    portfolio_service=Provide[DependencyContainer.portfolio_service],
):
    """Return a summary of the current backtest state.

    Aggregates counts from the order service and other services to
    provide a quick overview of backtest results.
    """
    from flask import jsonify
    return jsonify({
        "total_orders": order_service.count(request.args),
        "total_trades": trade_service.count(request.args),
        "total_positions": position_service.count(request.args),
    }), 200
