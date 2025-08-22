default_weights = {
    # Profitability
    "total_net_gain": 3.0,
    "total_net_loss": 0.0,
    "total_return": 0.0,
    "avg_return_per_trade": 0.0,

    # Risk-adjusted returns
    "sharpe_ratio": 1.0,
    "sortino_ratio": 1.0,
    "profit_factor": 1.0,

    # Risk
    "max_drawdown": -2.0,
    "max_drawdown_duration": -0.5,

    # Trading activity
    "number_of_trades": 2.0,
    "win_rate": 3.0,

    # Exposure
    "exposure_factor": 0.5,
    "exposure_ratio": 0.0,
    "exposure_time": 0.0,
}


def normalize(value, min_val, max_val):
    """
    Normalize a value to a range [0, 1].

    Args:
        value (float): The value to normalize.
        min_val (float): The minimum value of the range.
        max_val (float): The maximum value of the range.

    Returns:
        float: The normalized value.
    """
    if max_val == min_val:
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

        if key in ranges:
            value = normalize(value, ranges[key][0], ranges[key][1])
        score += weight * value
    return score


def create_weights(
    focus: str = "balanced",
    gain: float = 3.0,
    win_rate: float = 3.0,
    trades: float = 2.0,
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
        focus (str): One of [
            "balanced", "profit", "frequency", "risk_adjusted"
        ].
        gain (float): Weight for total_net_gain (default only).
        win_rate (float): Weight for win_rate (default only).
        trades (float): Weight for number_of_trades (default only).
        custom_weights (dict): Full override for weights (all metrics).
                               If provided, it takes precedence over presets.

    Returns:
        dict: A dictionary of weights for ranking backtests.
    """

    # default / balanced
    base = {
        "total_net_gain": gain,
        "win_rate": win_rate,
        "number_of_trades": trades,
        "sharpe_ratio": 1.0,
        "sortino_ratio": 1.0,
        "profit_factor": 1.0,
        "max_drawdown": -2.0,
        "max_drawdown_duration": -0.5,
        "total_net_loss": 0.0,
        "total_return": 0.0,
        "avg_return_per_trade": 0.0,
        "exposure_factor": 0.5,
        "exposure_ratio": 0.0,
        "exposure_time": 0.0,
    }

    # apply presets
    if focus == "profit":
        base.update({
            "total_net_gain": 5.0,
            "win_rate": 2.0,
            "number_of_trades": 1.0,
        })
    elif focus == "frequency":
        base.update({
            "number_of_trades": 4.0,
            "win_rate": 2.0,
            "total_net_gain": 2.0,
        })
    elif focus == "risk_adjusted":
        base.update({
            "sharpe_ratio": 3.0,
            "sortino_ratio": 3.0,
            "max_drawdown": -3.0,
        })

    # if full custom dict is given → override everything
    if custom_weights is not None:
        base = {**base, **custom_weights}

    return base


def rank_results(backtests, focus=None, weights=None):
    """
    Rank backtest results based on specified focus and weights.
    Args:
        backtests (list): List of backtest results to rank.
        focus (str, optional): Focus for ranking. If None,
            uses default weights. Options: "balanced", "profit",
            "frequency", "risk_adjusted".
        weights (dict, optional): Custom weights for ranking metrics.
            If None, uses default weights based on focus.

    Returns:
        list: Sorted list of backtests based on computed scores.
    """

    if weights is None:
        weights = create_weights(focus=focus)

    # First compute metric ranges for normalization
    ranges = {}
    for key in weights:
        values = [getattr(bt.backtest_metrics, key, None) for bt in backtests]
        values = [v for v in values if isinstance(v, (int, float))]
        if values:
            ranges[key] = (min(values), max(values))

    return sorted(
        backtests,
        key=lambda bt: compute_score(bt.backtest_metrics, weights, ranges),
        reverse=True
    )
