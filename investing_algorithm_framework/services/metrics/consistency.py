import math


def get_cv_consistency(values):
    """
    CV-based consistency: 1 - CV (CV = std / |mean|), capped [0, 1].

    Standard statistical measure; scale-invariant.
    Returns None if fewer than 2 values.
    Returns 0.0 when mean ≈ 0 (unstable).

    Args:
        values: list of numeric values (e.g. per-window returns)

    Returns:
        float in [0, 1] or None
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if abs(mean) < 1e-9:
        return 0.0
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    cv = math.sqrt(var) / abs(mean)
    return max(0.0, min(1.0, 1.0 - cv))


def get_normalized_stability(values, max_std):
    """
    Normalized-std stability: 1 - std/max_std, capped [0, 1].

    Uses a domain-specific max_std for normalization.
    More intuitive for bounded metrics (win rate 0-100,
    Sharpe typically -2 to +4).
    Returns None if fewer than 2 values.

    Args:
        values: list of numeric values (e.g. per-window win rates)
        max_std: domain-specific maximum standard deviation for
                 normalization

    Returns:
        float in [0, 1] or None
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    std = math.sqrt(var)
    return max(0.0, min(1.0, 1.0 - std / max_std))


def get_consistency_score(
    return_consistency,
    win_rate_consistency,
    sharpe_consistency,
    number_of_profitable_windows=None,
    number_of_windows=None,
):
    """
    Composite consistency score using weighted components:
    35% returns, 25% win rate, 20% Sharpe, 20% profitable window ratio.

    Args:
        return_consistency: CV consistency of per-window returns
        win_rate_consistency: CV consistency of per-window win rates
        sharpe_consistency: CV consistency of per-window Sharpe ratios
        number_of_profitable_windows: count of profitable windows
        number_of_windows: total number of windows

    Returns:
        float in [0, 1] or None
    """
    return _composite(
        return_consistency,
        win_rate_consistency,
        sharpe_consistency,
        number_of_profitable_windows,
        number_of_windows,
    )


def get_stability_score(
    return_stability,
    win_rate_stability,
    sharpe_stability,
    number_of_profitable_windows=None,
    number_of_windows=None,
):
    """
    Composite stability score using weighted components:
    35% returns, 25% win rate, 20% Sharpe, 20% profitable window ratio.

    Args:
        return_stability: normalized stability of per-window returns
        win_rate_stability: normalized stability of per-window win rates
        sharpe_stability: normalized stability of per-window Sharpe ratios
        number_of_profitable_windows: count of profitable windows
        number_of_windows: total number of windows

    Returns:
        float in [0, 1] or None
    """
    return _composite(
        return_stability,
        win_rate_stability,
        sharpe_stability,
        number_of_profitable_windows,
        number_of_windows,
    )


def _composite(
    ret_c, wr_c, sh_c,
    number_of_profitable_windows=None,
    number_of_windows=None,
):
    components = []
    weights_c = []
    if ret_c is not None:
        components.append(ret_c)
        weights_c.append(0.35)
    if wr_c is not None:
        components.append(wr_c)
        weights_c.append(0.25)
    if sh_c is not None:
        components.append(sh_c)
        weights_c.append(0.20)
    if number_of_windows and number_of_windows > 0 \
            and number_of_profitable_windows is not None:
        pw_ratio = number_of_profitable_windows / number_of_windows
        components.append(pw_ratio)
        weights_c.append(0.20)
    if not components:
        return None
    total_w = sum(weights_c)
    return sum(c * w for c, w in zip(components, weights_c)) / total_w
