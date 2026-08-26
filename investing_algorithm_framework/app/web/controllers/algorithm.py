import logging
import math

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework.services.metrics import (
    get_equity_curve,
    get_drawdown_series,
    get_max_drawdown,
    get_sharpe_ratio,
)
from investing_algorithm_framework.services.metrics.trades import (
    get_number_of_trades,
    get_number_of_open_trades,
    get_number_of_closed_trades,
)
from investing_algorithm_framework.services.metrics.win_rate import (
    get_win_rate,
)

logger = logging.getLogger("investing_algorithm_framework")

router = APIRouter()

DEFAULT_RISK_FREE_RATE = 0.04


def _finite_or_none(value):
    """JSON has no NaN/Infinity — convert non-finite floats to None."""
    if isinstance(value, (int, float)) and not math.isfinite(value):
        return None
    return value


@router.get("/api/algorithm/status")
@inject
def get_algorithm_status(
    algorithm_runner=Depends(Provide[DependencyContainer.algorithm_runner]),
):
    """Return whether the algorithm is currently running, stopped, or
    has not been started yet, along with its persisted enabled/disabled
    control state (the state a stateless deployment such as AWS Lambda
    or Azure Functions checks before each scheduled invocation).
    """
    return JSONResponse(content={
        **algorithm_runner.get_status_report(),
        "control": algorithm_runner.get_control_state(),
    }, status_code=200)


@router.post("/api/algorithm/start")
@inject
def start_algorithm(
    algorithm_runner=Depends(Provide[DependencyContainer.algorithm_runner]),
):
    """
    Enables the algorithm and, if running in live web mode, (re)starts
    its event loop in the background. The enabled flag is persisted to
    the resource directory (and pushed via the configured state
    handler, if any), so a stateless deployment (AWS Lambda, Azure
    Functions) also honors it on its next scheduled invocation.
    """
    try:
        started = algorithm_runner.start()
    except OperationalException as e:
        return JSONResponse(content={"error_message": str(e)}, status_code=409)

    return JSONResponse(content={
        "started": started,
        **algorithm_runner.get_status_report(),
        "control": algorithm_runner.get_control_state(),
    }, status_code=200)


@router.post("/api/algorithm/invoke")
@inject
def invoke_algorithm(
    request: Request,
    algorithm_runner=Depends(Provide[DependencyContainer.algorithm_runner]),
):
    """
    Forces the algorithm's strategies to run immediately, ignoring
    their configured schedule. The algorithm must already be running
    (see POST /api/algorithm/start). Pass one or more repeatable
    ``?strategy_id=`` query params to only invoke specific strategies;
    omit to invoke all of them.
    """
    strategy_ids = request.query_params.getlist("strategy_id") or None

    try:
        algorithm_runner.invoke_now(strategy_ids)
    except OperationalException as e:
        return JSONResponse(content={"error_message": str(e)}, status_code=409)

    return JSONResponse(content={
        "invoked": True,
        "strategy_ids": strategy_ids,
        **algorithm_runner.get_status_report(),
    }, status_code=200)


@router.post("/api/algorithm/stop")
@inject
def stop_algorithm(
    request: Request,
    algorithm_runner=Depends(Provide[DependencyContainer.algorithm_runner]),
):
    """
    Disables the algorithm and, if running in live web mode, signals
    its event loop to stop after it finishes its current iteration.
    Pass ``?wait=true`` to block the request until the loop has
    actually exited. The disabled flag is persisted (and pushed via
    the configured state handler, if any), so a stateless deployment
    (AWS Lambda, Azure Functions) skips its next scheduled invocation.
    Pass ``?reason=...`` to record why it was stopped.
    """
    wait = request.query_params.get("wait", "false").lower() \
        in ("1", "true", "yes")
    reason = request.query_params.get("reason")
    stopped = algorithm_runner.stop(wait=wait, reason=reason)
    return JSONResponse(content={
        "stopped": stopped,
        **algorithm_runner.get_status_report(),
        "control": algorithm_runner.get_control_state(),
    }, status_code=200)


@router.get("/api/algorithm/insights")
@inject
def get_algorithm_insights(
    request: Request,
    portfolio_snapshot_service=Depends(
        Provide[DependencyContainer.portfolio_snapshot_service]
    ),
    trade_service=Depends(Provide[DependencyContainer.trade_service]),
    portfolio_service=Depends(Provide[DependencyContainer.portfolio_service]),
):
    """
    Returns a summary of the trading algorithm's performance: equity
    curve, drawdown, key risk/return metrics, and trade/portfolio
    counts. Computed from the live portfolio snapshots and trades, so
    it becomes more meaningful the longer the algorithm has been
    running.
    """
    risk_free_rate = float(
        request.query_params.get("risk_free_rate", DEFAULT_RISK_FREE_RATE)
    )
    snapshots = portfolio_snapshot_service.get_all()
    trades = trade_service.get_all()
    portfolios = portfolio_service.get_all()

    equity_curve = get_equity_curve(snapshots)
    drawdown_series = get_drawdown_series(snapshots)

    insights = {
        "number_of_trades": get_number_of_trades(trades),
        "number_of_open_trades": get_number_of_open_trades(trades),
        "number_of_closed_trades": get_number_of_closed_trades(trades),
        "win_rate": _finite_or_none(get_win_rate(trades)),
        "max_drawdown": _finite_or_none(get_max_drawdown(snapshots)),
        "sharpe_ratio": _finite_or_none(
            get_sharpe_ratio(snapshots, risk_free_rate)
        ) if len(snapshots) > 1 else None,
        "equity_curve": [
            {"value": value, "datetime": timestamp.isoformat()}
            for value, timestamp in equity_curve
        ],
        "drawdown_series": [
            {"value": value, "datetime": timestamp.isoformat()}
            for value, timestamp in drawdown_series
        ],
        "portfolios": [
            {
                "identifier": portfolio.identifier,
                "trading_symbol": portfolio.trading_symbol,
                "unallocated": portfolio.unallocated,
            }
            for portfolio in portfolios
        ],
    }
    return JSONResponse(content=insights, status_code=200)
