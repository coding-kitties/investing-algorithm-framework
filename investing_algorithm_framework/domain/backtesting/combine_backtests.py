from typing import List

from investing_algorithm_framework.domain.backtesting import Backtest, BacktestDateRange
from investing_algorithm_framework.domain.backtesting import \
    BacktestSummaryMetrics


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
    backtest_date_range: BacktestDateRange = None
) -> Backtest:
    """
    Combine multiple backtests into a single backtest by aggregating
    their results.

    Args:
        backtests (List[Backtest]): List of Backtest instances to combine.
        backtest_date_range (BacktestDateRange, optional): The date range
            for the combined backtest.

    Returns:
        Backtest: A new Backtest instance representing the combined results.
    """
    backtest_metrics = []
    backtest_runs = []

    for backtest in backtests:
        backtest_metric = None
        backtest_run = None

        if backtest_date_range is not None:
            backtest_metric = \
                backtest.get_backtest_metrics(backtest_date_range)
            backtest_run = \
                backtest.get_backtest_run(backtest_date_range)
        else:
            backtest_run = backtest.backtest_runs[0] \
                if len(backtest.backtest_runs) > 0 else None

            if backtest_run is not None:
                backtest_metric = backtest_run.backtest_metrics

        if backtest_metric is not None:
            backtest_metrics.append(backtest_metric)
            backtest_runs.append(backtest_run)

    total_net_gain = sum(
        b.total_net_gain for b in backtest_metrics
        if b.total_net_gain is not None
    )
    average_total_net_gain = safe_weighted_mean(
        [b.total_net_gain for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_total_net_gain_percentage = safe_weighted_mean(
        [b.total_net_gain_percentage for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    total_net_gain_percentage = sum(
        b.total_net_gain_percentage for b in backtest_metrics
        if b.total_net_gain_percentage is not None
    )
    gross_loss = sum(
        b.gross_loss for b in backtest_metrics
        if b.gross_loss is not None
    )
    average_gross_loss = safe_weighted_mean(
        [b.gross_loss for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    growth = sum(
        b.growth for b in backtest_metrics
        if b.growth is not None
    )
    growth_percentage = sum(
        b.growth_percentage for b in backtest_metrics
        if b.growth_percentage is not None
    )
    average_growth = safe_weighted_mean(
        [b.growth for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    average_growth_percentage = safe_weighted_mean(
        [b.growth_percentage for b in backtest_metrics],
        [b.total_number_of_days for b in backtest_metrics]
    )
    trades_average_return = safe_weighted_mean(
        [b.trades_average_return for b in backtest_metrics],
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
    summary = BacktestSummaryMetrics(
        total_net_gain=total_net_gain,
        total_net_gain_percentage=total_net_gain_percentage,
        average_total_net_gain=average_total_net_gain,
        average_total_net_gain_percentage=average_total_net_gain_percentage,
        gross_loss=gross_loss,
        average_gross_loss=average_gross_loss,
        growth=growth,
        growth_percentage=growth_percentage,
        average_growth=average_growth,
        average_growth_percentage=average_growth_percentage,
        trades_average_return=trades_average_return,
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
        exposure_ratio=exposure_ratio
    )

    metadata = None

    # Get first non-empty metadata
    for backtest in backtests:
        if backtest.metadata:
            metadata = backtest.metadata
            break

    backtest = Backtest(
        backtest_summary=summary,
        metadata=metadata,
        backtest_runs=backtest_runs
    )
    return backtest
