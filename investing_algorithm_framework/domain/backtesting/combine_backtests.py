import logging
import math
from typing import List

from .consistency import (
    get_cv_consistency, get_normalized_stability,
    get_consistency_score, get_stability_score,
)
from .backtest_metrics import BacktestMetrics
from .backtest_summary_metrics import BacktestSummaryMetrics

logger = logging.getLogger("investing_algorithm_framework")


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


def _compound_percentage_returns(percentages):
    """
    Compound percentage returns across multiple periods.

    For example, if period 1 has 10% return and period 2 has 5% return,
    the compounded return is: (1 + 0.10) * (1 + 0.05) - 1 = 15.5%
    NOT simply 10% + 5% = 15%

    Args:
        percentages (List[float | None]): List of percentage returns
            (as whole numbers, e.g., 10 for 10%).

    Returns:
        float | None: The compounded percentage return, or None if no
            valid percentages.
    """
    valid_percentages = [p for p in percentages if p is not None]
    if not valid_percentages:
        return None

    # Convert percentages to decimals, compound, then convert back
    compounded = 1.0
    for pct in valid_percentages:
        compounded *= (1 + pct / 100)

    # Convert back to percentage
    return (compounded - 1) * 100


def combine_backtests(backtests):
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
    algorithm_id = None

    for backtest in backtests:
        if algorithm_id is None:
            algorithm_id = backtest.algorithm_id
        elif algorithm_id != backtest.algorithm_id:
            raise ValueError(
                "All backtests must belong to the same algorithm id"
                "to be combined."
            )

        backtest_runs += backtest.get_all_backtest_runs()
        backtest_metrics += backtest.get_all_backtest_metrics()

    summary = generate_backtest_summary_metrics(backtest_metrics)

    metadata = None
    risk_free_rate = None

    # Check if there are duplicate backtest runs
    unique_date_ranges = set()
    for backtest in backtests:
        for run in backtest.get_all_backtest_runs():
            date_range = (run.backtest_start_date, run.backtest_end_date)
            if date_range in unique_date_ranges:
                logger.warning(
                    "Duplicate backtest run detected for date range: "
                    f"{date_range} when combining backtests."
                )
            unique_date_ranges.add(date_range)

    # Merge all metadata dictionaries
    metadata = {}
    for backtest in backtests:
        if backtest.metadata:
            metadata.update(backtest.metadata)

    # Merge all parameters dictionaries
    parameters = {}
    for backtest in backtests:
        if backtest.parameters:
            parameters.update(backtest.parameters)

    # Get the first risk-free rate
    for backtest in backtests:
        if backtest.risk_free_rate is not None:
            risk_free_rate = backtest.risk_free_rate
            break
    from .backtest import Backtest

    backtest = Backtest(
        algorithm_id=algorithm_id,
        backtest_summary=summary,
        metadata=metadata,
        risk_free_rate=risk_free_rate,
        backtest_runs=backtest_runs,
        parameters=parameters
    )
    return backtest


def generate_backtest_summary_metrics(
    backtest_metrics: List[BacktestMetrics]
) -> BacktestSummaryMetrics:
    """
    Combine multiple BacktestMetrics into a single BacktestSummaryMetrics
    by aggregating their results.

    The aggregation logic follows these principles:
    - Absolute values (gains, losses, growth): summed across periods
    - Percentage returns: compounded across periods (not summed)
    - Ratios (Sharpe, Sortino, etc.): weighted average by time period
    - Trade-based metrics (win rate, avg trade return): weighted by trade count
    - Max drawdown: worst (minimum) value across all periods
    - Counts (number of trades): summed

    Args:
        backtest_metrics (List[BacktestMetrics]): List of BacktestMetrics
            instances to combine.

    Returns:
        BacktestSummaryMetrics: A new BacktestSummaryMetrics instance
            representing the combined results.
    """
    if not backtest_metrics:
        return BacktestSummaryMetrics()

    # Filter out None metrics
    valid_metrics = [b for b in backtest_metrics if b is not None]
    if not valid_metrics:
        return BacktestSummaryMetrics()

    # === ABSOLUTE VALUES (summed) ===
    total_net_gain = sum(
        b.total_net_gain for b in valid_metrics
        if b.total_net_gain is not None
    )
    total_loss = sum(
        b.gross_loss for b in valid_metrics
        if b.gross_loss is not None
    )
    total_growth = sum(
        b.total_growth for b in valid_metrics
        if b.total_growth is not None
    )

    # === PERCENTAGE RETURNS (compounded, not summed) ===
    # Compound returns: (1 + r1) * (1 + r2) * ... - 1
    # For percentages stored as whole numbers (e.g., 10 for 10%)
    total_net_gain_percentage = _compound_percentage_returns(
        [b.total_net_gain_percentage for b in valid_metrics]
    )
    total_loss_percentage = _compound_percentage_returns(
        [b.total_loss_percentage for b in valid_metrics]
    )
    total_growth_percentage = _compound_percentage_returns(
        [b.total_growth_percentage for b in valid_metrics]
    )

    # === AVERAGES (weighted by time) ===
    average_total_net_gain = safe_weighted_mean(
        [b.total_net_gain for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    average_total_net_gain_percentage = safe_weighted_mean(
        [b.total_net_gain_percentage for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    average_total_loss = safe_weighted_mean(
        [b.gross_loss for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    average_total_loss_percentage = safe_weighted_mean(
        [b.total_loss_percentage for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    average_growth = safe_weighted_mean(
        [b.total_growth for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    average_growth_percentage = safe_weighted_mean(
        [b.total_growth_percentage for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )

    # === RISK-ADJUSTED RATIOS (weighted by time) ===
    cagr = safe_weighted_mean(
        [b.cagr for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    sharpe_ratio = safe_weighted_mean(
        [b.sharpe_ratio for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    sortino_ratio = safe_weighted_mean(
        [b.sortino_ratio for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    calmar_ratio = safe_weighted_mean(
        [b.calmar_ratio for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    annual_volatility = safe_weighted_mean(
        [b.annual_volatility for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )

    # === PROFIT FACTOR (recalculated from totals, not averaged) ===
    # profit_factor = total_gross_profit / total_gross_loss
    total_gross_profit = sum(
        b.gross_profit for b in valid_metrics
        if hasattr(b, 'gross_profit') and b.gross_profit is not None
    )
    total_gross_loss_abs = abs(sum(
        b.gross_loss for b in valid_metrics
        if b.gross_loss is not None
    ))
    if total_gross_loss_abs > 0:
        profit_factor = total_gross_profit / total_gross_loss_abs
    else:
        # Fallback to weighted average if we can't calculate from totals
        profit_factor = safe_weighted_mean(
            [b.profit_factor for b in valid_metrics],
            [b.total_number_of_days for b in valid_metrics]
        )

    # === MAX DRAWDOWN (worst value = minimum,
    # since drawdowns are negative) ===
    drawdowns = [b.max_drawdown for b in valid_metrics
                 if b.max_drawdown is not None]
    max_drawdown = min(drawdowns) if drawdowns else None

    max_drawdown_duration = max(
        (b.max_drawdown_duration for b in valid_metrics
         if b.max_drawdown_duration is not None), default=None
    )

    # === TRADE FREQUENCY (weighted by time) ===
    trades_per_year = safe_weighted_mean(
        [b.trades_per_year for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    trades_per_month = (
        trades_per_year / 12 if trades_per_year is not None else None
    )
    trades_per_week = (
        trades_per_year / 52 if trades_per_year is not None else None
    )

    # === WIN RATE (weighted by number of closed trades, not time) ===
    win_rate = safe_weighted_mean(
        [b.win_rate for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )
    current_win_rate = safe_weighted_mean(
        [b.current_win_rate for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )

    # === WIN/LOSS RATIO (weighted by number of closed trades) ===
    win_loss_ratio = safe_weighted_mean(
        [b.win_loss_ratio for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )
    current_win_loss_ratio = safe_weighted_mean(
        [b.current_win_loss_ratio for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )

    # === TRADE COUNTS (summed) ===
    number_of_trades = sum(
        b.number_of_trades for b in valid_metrics
        if b.number_of_trades is not None
    )
    number_of_trades_closed = sum(
        b.number_of_trades_closed for b in valid_metrics
        if b.number_of_trades_closed is not None
    )

    # === EXPOSURE (weighted by time) ===
    cumulative_exposure = safe_weighted_mean(
        [b.cumulative_exposure for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )
    exposure_ratio = safe_weighted_mean(
        [b.exposure_ratio for b in valid_metrics],
        [b.total_number_of_days for b in valid_metrics]
    )

    # === AVERAGE TRADE RETURN (weighted by total trades) ===
    average_trade_return = safe_weighted_mean(
        [b.average_trade_return for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )
    average_trade_return_percentage = safe_weighted_mean(
        [b.average_trade_return_percentage for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )

    # === AVERAGE TRADE LOSS (weighted by losing trades) ===
    # We need to estimate losing trade count from win_rate if not available
    losing_trade_weights = []
    for b in valid_metrics:
        if b.number_of_trades_closed is not None and b.win_rate is not None:
            losing_trades = b.number_of_trades_closed * (1 - b.win_rate / 100)
            losing_trade_weights.append(losing_trades)
        else:
            losing_trade_weights.append(b.number_of_trades_closed or 0)

    average_trade_loss = safe_weighted_mean(
        [b.average_trade_loss for b in valid_metrics],
        losing_trade_weights
    )
    average_trade_loss_percentage = safe_weighted_mean(
        [b.average_trade_loss_percentage for b in valid_metrics],
        losing_trade_weights
    )

    # === AVERAGE TRADE GAIN (weighted by winning trades) ===
    winning_trade_weights = []
    for b in valid_metrics:
        if b.number_of_trades_closed is not None and b.win_rate is not None:
            winning_trades = b.number_of_trades_closed * (b.win_rate / 100)
            winning_trade_weights.append(winning_trades)
        else:
            winning_trade_weights.append(b.number_of_trades_closed or 0)

    average_trade_gain = safe_weighted_mean(
        [b.average_trade_gain for b in valid_metrics],
        winning_trade_weights
    )
    average_trade_gain_percentage = safe_weighted_mean(
        [b.average_trade_gain_percentage for b in valid_metrics],
        winning_trade_weights
    )

    # === WINDOW COUNTS ===
    number_of_windows = len(valid_metrics)
    number_of_profitable_windows = sum(
        1 for b in valid_metrics
        if b.total_net_gain is not None and b.total_net_gain > 0
    )
    number_of_windows_with_trades = sum(
        1 for b in valid_metrics
        if b.number_of_trades_closed is not None
        and b.number_of_trades_closed > 0
    )

    # === VaR / CVaR (weighted by time) ===
    var_95_values = [
        b.var_95 for b in valid_metrics
        if hasattr(b, 'var_95') and isinstance(
            getattr(b, 'var_95', None), (int, float)
        )
    ]
    var_95_weights = [
        b.total_number_of_days for b in valid_metrics
        if hasattr(b, 'var_95') and isinstance(
            getattr(b, 'var_95', None), (int, float)
        )
    ]
    var_95 = safe_weighted_mean(var_95_values, var_95_weights)

    cvar_95_values = [
        b.cvar_95 for b in valid_metrics
        if hasattr(b, 'cvar_95') and isinstance(
            getattr(b, 'cvar_95', None), (int, float)
        )
    ]
    cvar_95_weights = [
        b.total_number_of_days for b in valid_metrics
        if hasattr(b, 'cvar_95') and isinstance(
            getattr(b, 'cvar_95', None), (int, float)
        )
    ]
    cvar_95 = safe_weighted_mean(cvar_95_values, cvar_95_weights)

    # === TRADE DURATIONS (weighted by number of closed trades) ===
    average_trade_duration = safe_weighted_mean(
        [b.average_trade_duration for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )
    average_win_duration = safe_weighted_mean(
        [b.average_win_duration for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )
    average_loss_duration = safe_weighted_mean(
        [b.average_loss_duration for b in valid_metrics],
        [b.number_of_trades_closed for b in valid_metrics]
    )

    # === CONSECUTIVE STREAKS (worst/best across all windows) ===
    consecutive_wins = [
        b.max_consecutive_wins for b in valid_metrics
        if b.max_consecutive_wins is not None
        and isinstance(b.max_consecutive_wins, (int, float))
    ]
    max_consecutive_wins = max(consecutive_wins) if consecutive_wins else None

    consecutive_losses = [
        b.max_consecutive_losses for b in valid_metrics
        if b.max_consecutive_losses is not None
        and isinstance(b.max_consecutive_losses, (int, float))
    ]
    max_consecutive_losses = max(
        consecutive_losses
    ) if consecutive_losses else None

    # === CONSISTENCY METRICS ===
    return_consistency = None
    win_rate_consistency = None
    sharpe_consistency = None
    consistency_score_val = None
    return_stability = None
    win_rate_stability = None
    sharpe_stability = None
    stability_score_val = None

    if len(valid_metrics) >= 2:
        # --- Per-window returns ---
        per_window_returns = [
            b.total_net_gain_percentage for b in valid_metrics
            if b.total_net_gain_percentage is not None
        ]
        return_consistency = get_cv_consistency(per_window_returns)
        return_stability = get_normalized_stability(
            per_window_returns, 100.0
        )

        # --- Per-window win rates ---
        per_window_win_rates = [
            b.win_rate for b in valid_metrics
            if b.win_rate is not None
            and b.number_of_trades_closed is not None
            and b.number_of_trades_closed > 0
        ]
        win_rate_consistency = get_cv_consistency(per_window_win_rates)
        win_rate_stability = get_normalized_stability(
            per_window_win_rates, 50.0
        )

        # --- Per-window Sharpe ratios ---
        per_window_sharpe = [
            b.sharpe_ratio for b in valid_metrics
            if b.sharpe_ratio is not None
            and not math.isnan(b.sharpe_ratio)
            and not math.isinf(b.sharpe_ratio)
        ]
        sharpe_consistency = get_cv_consistency(per_window_sharpe)
        sharpe_stability = get_normalized_stability(
            per_window_sharpe, 2.0
        )

        # --- Composite scores ---
        consistency_score_val = get_consistency_score(
            return_consistency, win_rate_consistency, sharpe_consistency,
            number_of_profitable_windows, number_of_windows,
        )
        stability_score_val = get_stability_score(
            return_stability, win_rate_stability, sharpe_stability,
            number_of_profitable_windows, number_of_windows,
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
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        profit_factor=profit_factor,
        annual_volatility=annual_volatility,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_drawdown_duration,
        trades_per_year=trades_per_year,
        trades_per_month=trades_per_month,
        trades_per_week=trades_per_week,
        win_rate=win_rate,
        current_win_rate=current_win_rate,
        win_loss_ratio=win_loss_ratio,
        current_win_loss_ratio=current_win_loss_ratio,
        number_of_trades=number_of_trades,
        number_of_trades_closed=number_of_trades_closed,
        cumulative_exposure=cumulative_exposure,
        exposure_ratio=exposure_ratio,
        average_trade_return=average_trade_return,
        average_trade_return_percentage=average_trade_return_percentage,
        average_trade_loss=average_trade_loss,
        average_trade_loss_percentage=average_trade_loss_percentage,
        average_trade_gain=average_trade_gain,
        average_trade_gain_percentage=average_trade_gain_percentage,
        number_of_windows=number_of_windows,
        number_of_profitable_windows=number_of_profitable_windows,
        number_of_windows_with_trades=number_of_windows_with_trades,
        var_95=var_95,
        cvar_95=cvar_95,
        average_trade_duration=average_trade_duration,
        average_win_duration=average_win_duration,
        average_loss_duration=average_loss_duration,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        return_consistency=return_consistency,
        win_rate_consistency=win_rate_consistency,
        sharpe_consistency=sharpe_consistency,
        consistency_score=consistency_score_val,
        return_stability=return_stability,
        win_rate_stability=win_rate_stability,
        sharpe_stability=sharpe_stability,
        stability_score=stability_score_val,
    )
