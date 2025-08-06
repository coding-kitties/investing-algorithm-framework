from investing_algorithm_framework.domain import Backtest

defaults_ranking_weights = {
    "total_return": 2.0,
    "sharpe_ratio": 1.0,
    "sortino_ratio": 1.0,
    "win_rate": 1.0,
    "profit_factor": 1.0,
    "max_drawdown": -1.0,  # negative weight to penalize high drawdown
    "max_drawdown_duration": -0.5,  # penalize long drawdown periods
    "number_of_trades": 0.5,
    "exposure_factor": 0.5,
}


def compute_score(metrics: dict, weights: dict) -> float:
    score = 0
    for key, weight in weights.items():

        # Metrics are attributeds to the backtest
        if not hasattr(metrics, key):
            continue

        # Get the value of the metric
        value = getattr(metrics, key)

        try:
            score += weight * value
        except TypeError:
            continue  # skip if value is not a number
    return score


def rank_results(
    backtests: list[Backtest], weights=defaults_ranking_weights
) -> list[Backtest]:
    """
    Rank backtests based on their metrics and the provided weights.

    The default weights are defined in `defaults_ranking_weights`.
    Please note that the weights should be adjusted based on the
    specific analysis needs. You can modify the `weights` parameter
    to include or exclude metrics as needed and reuse
    the `defaults_ranking_weights` as a starting point.

    Args:
        backtests (list[Backtest]): List of Backtest objects to rank.
        weights (dict): Weights for each metric to compute the score.

    Returns:
        list[Backtest]: List of Backtest objects sorted by
            their computed score.
    """
    return sorted(
        backtests,
        key=lambda bt: compute_score(bt.backtest_metrics, weights),
        reverse=True
    )
