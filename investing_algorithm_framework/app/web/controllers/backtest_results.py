import logging

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from werkzeug.datastructures import MultiDict

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

router = APIRouter()


def _query(request: Request) -> MultiDict:
    return MultiDict(request.query_params.multi_items())


@router.get("/api/backtest-results/orders")
@inject
def list_backtest_orders(
    request: Request,
    order_service=Depends(Provide[DependencyContainer.order_service]),
):
    """List all orders from the current backtest run.

    Supports the same query-parameter filters as ``/api/orders``
    (e.g. ``?status=CLOSED&portfolio=default``).
    """
    orders = order_service.get_all(_query(request))
    return create_response(orders, BacktestRunOrderSerializer())


@router.get("/api/backtest-results/orders/count")
@inject
def count_backtest_orders(
    request: Request,
    order_service=Depends(Provide[DependencyContainer.order_service]),
):
    """Return the count of orders matching the given filters."""
    count = order_service.count(_query(request))
    return JSONResponse(content={"count": count}, status_code=200)


@router.get("/api/backtest-results/trades")
@inject
def list_backtest_trades(
    request: Request,
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
):
    """List all trades from the current backtest run."""
    trades = trade_service.get_all(_query(request))
    return create_response(trades, BacktestRunTradeSerializer())


@router.get("/api/backtest-results/trades/count")
@inject
def count_backtest_trades(
    request: Request,
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
):
    """Return the count of trades matching the given filters."""
    count = trade_service.count(_query(request))
    return JSONResponse(content={"count": count}, status_code=200)


@router.get("/api/backtest-results/positions")
@inject
def list_backtest_positions(
    request: Request,
    position_service=Depends(Provide[DependencyContainer.position_service]),
):
    """List all positions from the current backtest run."""
    positions = position_service.get_all(_query(request))
    return create_response(positions, BacktestRunPositionSerializer())


@router.get("/api/backtest-results/positions/count")
@inject
def count_backtest_positions(
    request: Request,
    position_service=Depends(Provide[DependencyContainer.position_service]),
):
    """Return the count of positions matching the given filters."""
    count = position_service.count(_query(request))
    return JSONResponse(content={"count": count}, status_code=200)


@router.get("/api/backtest-results/portfolio-snapshots")
@inject
def list_backtest_portfolio_snapshots(
    request: Request,
    portfolio_snapshot_service=Depends(
        Provide[DependencyContainer.portfolio_snapshot_service]
    ),
):
    """List all portfolio snapshots from the current backtest run."""
    snapshots = portfolio_snapshot_service.get_all(_query(request))
    return create_response(snapshots, PortfolioSnapshotSerializer())


@router.get("/api/backtest-results/portfolio-snapshots/count")
@inject
def count_backtest_portfolio_snapshots(
    request: Request,
    portfolio_snapshot_service=Depends(
        Provide[DependencyContainer.portfolio_snapshot_service]
    ),
):
    """Return the count of portfolio snapshots matching the given filters."""
    count = portfolio_snapshot_service.count(_query(request))
    return JSONResponse(content={"count": count}, status_code=200)


@router.get("/api/backtest-results/metrics")
@inject
def get_backtest_metrics(
    request: Request,
    order_service=Depends(Provide[DependencyContainer.order_service]),
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
    position_service=Depends(Provide[DependencyContainer.position_service]),
    portfolio_service=Depends(Provide[DependencyContainer.portfolio_service]),
):
    """Return a summary of the current backtest state.

    Aggregates counts from the order service and other services to
    provide a quick overview of backtest results.
    """
    return JSONResponse(content={
        "total_orders": order_service.count(_query(request)),
        "total_trades": trade_service.count(_query(request)),
        "total_positions": position_service.count(_query(request)),
    }, status_code=200)
