import math

from investing_algorithm_framework.domain import BacktestEvaluationFocus
BacktestEvaluationFocus


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
        if value is None or (
            isinstance(value, float) and
            (math.isnan(value) or math.isinf(value))
        ):
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
        gain (float): Weight for total_net_gain (default only).
        win_rate (float): Weight for win_rate (default only).
        trades (float): Weight for number_of_trades (default only).
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


def rank_results(backtests, focus=None, weights=None, filter_fn=None):
    """
    Rank backtest results based on specified focus, weights, and filters.

    Args:
        backtests (list): List of backtest results to rank.
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

    Returns:
        list: Sorted list of backtests based on computed scores.
    """

    if weights is None:
        weights = create_weights(focus=focus)

    # Apply filtering
    if filter_fn is not None:
        if callable(filter_fn):
            backtests = [
                bt for bt in backtests
                if filter_fn(bt.backtest_metrics)
            ]
        elif isinstance(filter_fn, dict):
            backtests = [
                bt for bt in backtests
                if all(
                    cond(getattr(bt.backtest_metrics, key, None))
                    for key, cond in filter_fn.items()
                )
            ]

    # First compute metric ranges for normalization
    ranges = {}
    for key in weights:
        values = [getattr(bt.backtest_metrics, key, None) for bt in backtests]
        values = [
            v for v in values
            if isinstance(v, (int, float)) and v is not None
            and not math.isnan(v) and not math.isinf(v)
        ]

        if values:
            ranges[key] = (min(values), max(values))

    return sorted(
        backtests,
        key=lambda bt: compute_score(bt.backtest_metrics, weights, ranges),
        reverse=True
    )
