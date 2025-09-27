from typing import List

from .backtest import Backtest
from .backtest_summary_metrics import BacktestSummaryMetrics
from .backtest_metrics import BacktestMetrics


def safe_weighted_mean(values, weights):
    """
    Calculate the weighted mean of a list of values,
    ignoring None values and weights <= 0.

    Args:
        values (List[float | None]): List of values to average.
        weights (List[float | None]): Corresponding weights for the values.

    Returns:
        float | None: The weighted mean, or None if no valid values.
    """
    vals = [(v, w) for v, w in zip(values, weights) if
            v is not None and w is not None and w > 0]
    if not vals:
        return None
    total_weight = sum(w for _, w in vals)
    return sum(
        v * w for v, w in vals
    ) / total_weight if total_weight > 0 else None


def combine_backtests(
    backtests: List[Backtest],
) -> Backtest:
    """
    Combine multiple backtests into a single backtest by aggregating
    their results.

    Args:
        backtests (List[Backtest]): List of Backtest instances to combine.

    Returns:
        Backtest: A new Backtest instance representing the combined results.
    """
    backtest_metrics = []
    backtest_runs = []

    for backtest in backtests:
        backtest_metric = None
        backtest_run = backtest.backtest_runs[0] \
            if len(backtest.backtest_runs) > 0 else None

        if backtest_run is not None:
            backtest_metric = backtest_run.backtest_metrics

        if backtest_metric is not None:
            backtest_metrics.append(backtest_metric)
            backtest_runs.append(backtest_run)

    summary = generate_backtest_summary_metrics(backtest_metrics)

    metadata = None
    risk_free_rate = None

    # Get first non-empty metadata
    for backtest in backtests:
        if backtest.metadata:
            metadata = backtest.metadata
            break

    # Get the first risk-free rate
    for backtest in backtests:
        if backtest.risk_free_rate is not None:
            risk_free_rate = backtest.risk_free_rate
            break

    backtest = Backtest(
        backtest_summary=summary,
        metadata=metadata,
        risk_free_rate=risk_free_rate,
        backtest_runs=backtest_runs
    )
    return backtest


def generate_backtest_summary_metrics(
    backtest_metrics: List[BacktestMetrics]
) -> BacktestSummaryMetrics:
    """
    Combine multiple BacktestMetrics into a single BacktestMetrics
    by aggregating their results.

    Args:
        backtest_metrics (List[BacktestMetrics]): List of BacktestMetrics
            instances to combine.

    Returns:
        BacktestMetrics: A new BacktestMetrics instance representing the
            combined results.
    """
    total_net_gain = sum(
        b.total_net_gain for b in backtest_metrics
        if b.total_net_gain is not None
    )
    total_net_gain_percentage = sum(
        b.total_net_gain_percentage for b in backtest_metrics
        if b.total_net_gain_percentage is not None
    )
    average_total_net_gain = safe_weighted_mean(
        [b.total_net_gain for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_total_net_gain_percentage = safe_weighted_mean(
        [b.total_net_gain_percentage for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    total_loss = sum(
        b.gross_loss for b in backtest_metrics
        if b.gross_loss is not None
    )
    total_loss_percentage = sum(
        b.total_loss_percentage for b in backtest_metrics
        if b.total_loss_percentage is not None
    )
    average_total_loss = safe_weighted_mean(
        [b.gross_loss for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_total_loss_percentage = safe_weighted_mean(
        [b.total_loss_percentage for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    total_growth = sum(
        b.total_growth for b in backtest_metrics
        if b.total_growth is not None
    )
    total_growth_percentage = sum(
        b.total_growth_percentage for b in backtest_metrics
        if b.total_growth_percentage is not None
    )
    average_growth = safe_weighted_mean(
        [b.total_growth for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_growth_percentage = safe_weighted_mean(
        [b.total_growth_percentage for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    cagr = safe_weighted_mean(
        [b.cagr for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    sharp_ratio = safe_weighted_mean(
        [b.sharpe_ratio for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    sortino_ratio = safe_weighted_mean(
        [b.sortino_ratio for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    calmar_ratio = safe_weighted_mean(
        [b.calmar_ratio for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    profit_factor = safe_weighted_mean(
        [b.profit_factor for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    annual_volatility = safe_weighted_mean(
        [b.annual_volatility for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    max_drawdown = max(
        (b.max_drawdown for b in backtest_metrics
         if b.max_drawdown is not None), default=None
    )
    max_drawdown_duration = max(
        (b.max_drawdown_duration for b in backtest_metrics
            if b.max_drawdown_duration is not None), default=None
    )
    trades_per_year = safe_weighted_mean(
        [b.trades_per_year for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    win_rate = safe_weighted_mean(
        [b.win_rate for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    win_loss_ratio = safe_weighted_mean(
        [b.win_loss_ratio for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    number_of_trades = sum(
        b.number_of_trades for b in backtest_metrics
        if b.number_of_trades is not None
    )
    cumulative_exposure = safe_weighted_mean(
        [b.cumulative_exposure for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    exposure_ratio = safe_weighted_mean(
        [b.exposure_ratio for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_trade_return = safe_weighted_mean(
        [b.average_trade_return for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    average_trade_return_percentage = safe_weighted_mean(
        [b.average_trade_return_percentage for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    average_trade_loss = safe_weighted_mean(
        [b.average_trade_loss for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    average_trade_loss_percentage = safe_weighted_mean(
        [b.average_trade_loss_percentage for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    average_trade_gain = safe_weighted_mean(
        [b.average_trade_gain for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    average_trade_gain_percentage = safe_weighted_mean(
        [b.average_trade_gain_percentage for b in backtest_metrics],
        [b.number_of_trades for b in backtest_metrics]
    )
    return BacktestSummaryMetrics(
        total_net_gain=total_net_gain,
        total_net_gain_percentage=total_net_gain_percentage,
        average_net_gain=average_total_net_gain,
        average_net_gain_percentage=average_total_net_gain_percentage,
        total_loss=total_loss,
        total_loss_percentage=total_loss_percentage,
        average_loss=average_total_loss,
        average_loss_percentage=average_total_loss_percentage,
        total_growth=total_growth,
        total_growth_percentage=total_growth_percentage,
        average_growth=average_growth,
        average_growth_percentage=average_growth_percentage,
        cagr=cagr,
        sharpe_ratio=sharp_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        profit_factor=profit_factor,
        annual_volatility=annual_volatility,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_drawdown_duration,
        trades_per_year=trades_per_year,
        win_rate=win_rate,
        win_loss_ratio=win_loss_ratio,
        number_of_trades=number_of_trades,
        cumulative_exposure=cumulative_exposure,
        exposure_ratio=exposure_ratio,
        average_trade_return=average_trade_return,
        average_trade_return_percentage=average_trade_return_percentage,
        average_trade_loss=average_trade_loss,
        average_trade_loss_percentage=average_trade_loss_percentage,
        average_trade_gain=average_trade_gain,
        average_trade_gain_percentage=average_trade_gain_percentage
    )


def create_backtest_summary_metrics(
    backtest_metrics: List[BacktestMetrics]
) -> BacktestSummaryMetrics:
    """
    Create a combined BacktestSummaryMetrics from multiple backtests.

    Args:
        backtest_metrics (List[BacktestMetrics]): List of BacktestMetrics
            instances.

    Returns:
        BacktestSummaryMetrics: Combined summary metrics.
    """
