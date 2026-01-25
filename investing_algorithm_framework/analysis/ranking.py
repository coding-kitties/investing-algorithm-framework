import math
from typing import List
from statistics import mean

from investing_algorithm_framework.domain import BacktestEvaluationFocus, \
    BacktestDateRange, Backtest, BacktestMetrics, OperationalException


def normalize(value, min_val, max_val):
    """
    Normalize a value to a range [0, 1].
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return 0
    if min_val == max_val:
        return 0
    return (value - min_val) / (max_val - min_val)


def compute_score(metrics, weights, ranges):
    """
    Compute a weighted score for the given metrics.

    Args:
        metrics: The metrics to evaluate.
        weights: The weights to apply to each metric.
        ranges: The min/max ranges for each metric.

    Returns:
        float: The computed score.
    """
    score = 0
    for key, weight in weights.items():
        if not hasattr(metrics, key):
            continue
        value = getattr(metrics, key)
        # Skip non-numeric values (e.g., Trade objects
        # for best_trade/worst_trade)
        if not isinstance(value, (int, float)):
            continue
        if value is None or math.isnan(value) or math.isinf(value):
            continue
        if key in ranges:
            value = normalize(value, ranges[key][0], ranges[key][1])
        score += weight * value
    return score


def create_weights(
    focus: BacktestEvaluationFocus | str | None = None,
    custom_weights: dict | None = None,
) -> dict:
    """
    Utility to generate weights dicts for ranking backtests.

    This function does not assign weights to every possible performance
    metric. Instead, it focuses on a curated subset of commonly relevant
    ones (profitability, win rate, trade frequency, and risk-adjusted returns).
    The rationale is to avoid overfitting ranking logic to noisy or redundant
    statistics (e.g., monthly return breakdowns, best/worst trade), while
    keeping the weighting system simple and interpretable.
    Users who need fine-grained control can pass `custom_weights` to fully
    override defaults.

    Args:
        focus (BacktestEvaluationFocus | str | None): The focus for ranking.
        custom_weights (dict): Full override for weights (all metrics).
                               If provided, it takes precedence over presets.

    Returns:
        dict: A dictionary of weights for ranking backtests.
    """
    if focus is None:
        focus = BacktestEvaluationFocus.BALANCED

    weights = focus.get_weights()

    # if full custom dict is given → override everything
    if custom_weights is not None:
        weights = {**weights, **custom_weights}

    return weights


def rank_results(
    backtests: List[Backtest],
    focus=None,
    weights=None,
    filter_fn=None,
    backtest_date_range: BacktestDateRange = None
) -> List[Backtest]:
    """
    Rank backtest results based on specified focus, weights, and filters.

    Args:
        backtests (List[Backtest]): List of backtest results to rank.
        focus (str, optional): Focus for ranking. If None,
            uses default weights. Options: "balanced", "profit",
            "frequency", "risk_adjusted".
        weights (dict, optional): Custom weights for ranking metrics.
            If None, uses default weights based on focus.
        filter_fn (callable | dict, optional): A filter to apply to
            backtests before ranking.
            - If callable: receives metrics and should return True/False.
            - If dict: mapping {metric_name: condition_fn},
              all conditions must pass.
        backtest_date_range (BacktestDateRange, optional): If provided,
            only backtests matching this date range are considered.

    Returns:
        List[Backtest]: Sorted list of backtests based on computed scores.
    """

    if weights is None:
        weights = create_weights(focus=focus)

    # Pair backtests with their metrics
    paired = []
    for backtest in backtests:
        if backtest_date_range is not None:
            metrics = backtest.get_backtest_metrics(backtest_date_range)
        else:
            metrics = backtest.backtest_summary

        if metrics is not None:
            paired.append((backtest, metrics))

    # Apply filtering on metrics
    if filter_fn is not None:
        if callable(filter_fn):
            paired = [
                (bt, m) for bt, m in paired if filter_fn(m)
            ]
        elif isinstance(filter_fn, dict):
            paired = [
                (bt, m) for bt, m in paired
                if all(
                    cond(getattr(m, key, None))
                    for key, cond in filter_fn.items()
                )
            ]

    # Compute normalization ranges
    ranges = {}
    for key in weights:
        values = [
            getattr(m, key, None) for _, m in paired
        ]
        values = [
            v for v in values
            if isinstance(v, (int, float)) and v is not None
            and not math.isnan(v) and not math.isinf(v)
        ]
        if values:
            ranges[key] = (min(values), max(values))

    # Sort Backtests by score
    ranked = sorted(
        paired,
        key=lambda bm: compute_score(bm[1], weights, ranges),
        reverse=True
    )

    return [bt for bt, _ in ranked]


def combine_backtest_metrics(
    backtest_metrics: List[BacktestMetrics]
) -> BacktestMetrics:
    """
    Combine backtest metrics from multiple backtests into a single list.

    Args:
        backtest_metrics (List[BacktestMetrics]): List of backtest
            metrics to combine.

    Returns:
        BacktestMetrics: Combined list of backtest metrics.
    """
    if not backtest_metrics:
        raise OperationalException("No BacktestMetrics provided")

        # Helper to take mean safely

    def safe_mean(values):
        vals = [v for v in values if v is not None]
        return mean(vals) if vals else 0.0

        # Dates

    start_date = min(m.backtest_start_date for m in backtest_metrics)
    end_date = max(m.backtest_end_date for m in backtest_metrics)

    # Aggregate
    return BacktestMetrics(
        backtest_start_date=start_date,
        backtest_end_date=end_date,
        equity_curve=[],  # leave empty to avoid misleading curves
        total_growth=safe_mean([m.total_growth for m in backtest_metrics]),
        total_growth_percentage=safe_mean(
            [m.total_growth_percentage for m in backtest_metrics]),
        total_net_gain=safe_mean([m.total_net_gain for m in backtest_metrics]),
        total_net_gain_percentage=safe_mean(
            [m.total_net_gain_percentage for m in backtest_metrics]),
        final_value=safe_mean([m.final_value for m in backtest_metrics]),
        cagr=safe_mean([m.cagr for m in backtest_metrics]),
        sharpe_ratio=safe_mean([m.sharpe_ratio for m in backtest_metrics]),
        rolling_sharpe_ratio=[],
        sortino_ratio=safe_mean([m.sortino_ratio for m in backtest_metrics]),
        calmar_ratio=safe_mean([m.calmar_ratio for m in backtest_metrics]),
        profit_factor=safe_mean([m.profit_factor for m in backtest_metrics]),
        gross_profit=sum(m.gross_profit or 0 for m in backtest_metrics),
        gross_loss=sum(m.gross_loss or 0 for m in backtest_metrics),
        annual_volatility=safe_mean(
            [m.annual_volatility for m in backtest_metrics]),
        monthly_returns=[],
        yearly_returns=[],
        drawdown_series=[],
        max_drawdown=max(m.max_drawdown for m in backtest_metrics),
        max_drawdown_absolute=max(
            m.max_drawdown_absolute for m in backtest_metrics),
        max_daily_drawdown=max(m.max_daily_drawdown for m in backtest_metrics),
        max_drawdown_duration=max(
            m.max_drawdown_duration for m in backtest_metrics),
        trades_per_year=safe_mean(
            [m.trades_per_year for m in backtest_metrics]
        ),
        trade_per_day=safe_mean([m.trade_per_day for m in backtest_metrics]),
        exposure_ratio=safe_mean(
            [m.exposure_ratio for m in backtest_metrics]
        ),
        average_trade_gain=safe_mean(
            [m.average_trade_gain for m in backtest_metrics]),
        average_trade_gain_percentage=(
            safe_mean(
                [m.average_trade_gain_percentage for m in backtest_metrics]
            )
        ),
        average_trade_loss=safe_mean(
            [m.average_trade_loss for m in backtest_metrics]),
        average_trade_loss_percentage=(
            safe_mean(
                [m.average_trade_loss_percentage for m in backtest_metrics]
            )
        ),
        median_trade_return=safe_mean(
            [m.median_trade_return for m in backtest_metrics]),
        median_trade_return_percentage=(
            safe_mean(
                [m.median_trade_return_percentage for m in backtest_metrics]
            )
        ),
        best_trade=max((
            m.best_trade for m in backtest_metrics if m.best_trade),
            key=lambda t: t.net_gain if t else float('-inf'),
            default=None
        ),
        worst_trade=min(
            (m.worst_trade for m in backtest_metrics if m.worst_trade),
            key=lambda t: t.net_gain if t else float('inf'),
            default=None
        ),
        average_trade_duration=safe_mean(
            [m.average_trade_duration for m in backtest_metrics]),
        number_of_trades=sum(m.number_of_trades for m in backtest_metrics),
        win_rate=safe_mean([m.win_rate for m in backtest_metrics]),
        win_loss_ratio=safe_mean([m.win_loss_ratio for m in backtest_metrics]),
        percentage_winning_months=safe_mean(
            [m.percentage_winning_months for m in backtest_metrics]),
        percentage_winning_years=safe_mean(
            [m.percentage_winning_years for m in backtest_metrics]),
        average_monthly_return=safe_mean(
            [m.average_monthly_return for m in backtest_metrics]),
        average_monthly_return_losing_months=safe_mean(
            [m.average_monthly_return_losing_months for m in backtest_metrics]
        ),
        average_monthly_return_winning_months=safe_mean(
            [m.average_monthly_return_winning_months for m in backtest_metrics]
        ),
        best_month=max(
            (m.best_month for m in backtest_metrics if m.best_month),
            key=lambda x: x[0] if x else float('-inf'),
            default=None
        ),
        best_year=max((m.best_year for m in backtest_metrics if m.best_year),
                      key=lambda x: x[0] if x else float('-inf'),
                      default=None),
        worst_month=min(
            (m.worst_month for m in backtest_metrics if m.worst_month),
            key=lambda x: x[0] if x else float('inf'),
            default=None
        ),
        worst_year=min(
            (m.worst_year for m in backtest_metrics if m.worst_year),
            key=lambda x: x[0] if x else float('inf'),
            default=None
        ),
    )
