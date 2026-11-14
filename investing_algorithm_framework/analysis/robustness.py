"""Cross-study robustness ranking: does a strategy's edge hold up
across out-of-sample regimes, or was it only found by screening
in-sample?
"""

from typing import Any, Dict, List, Optional, Union

from investing_algorithm_framework.domain import BacktestEvaluationFocus

from .markdown import _get_summary


def _resolve_weights(
    focus: Optional[Union["BacktestEvaluationFocus", str]],
    weights: Optional[Dict[str, float]],
) -> Dict[str, float]:
    resolved: Dict[str, float] = {}
    if focus is not None:
        if isinstance(focus, str):
            focus = BacktestEvaluationFocus.from_string(focus)
        resolved.update(focus.get_weights())
    if weights:
        resolved.update(weights)
    return resolved


def _held_up_ratio(
    baseline_value: Optional[float],
    oos_value: Optional[float],
    weight: float,
) -> Optional[float]:
    """Ratio oriented so higher always means "held up better",
    regardless of whether *weight* favours higher or lower raw
    values (e.g. a penalty metric like ``max_drawdown``)."""
    if baseline_value is None or oos_value is None:
        return None
    if weight >= 0:
        if baseline_value == 0:
            return None
        return oos_value / baseline_value
    if oos_value == 0:
        return None
    return baseline_value / oos_value


def rank_by_cross_study_robustness(
    backtests: List[Any],
    studies: List[Any],
    baseline_study: Any,
    focus: Optional[Union["BacktestEvaluationFocus", str]] =
    BacktestEvaluationFocus.BALANCED,
    weights: Optional[Dict[str, float]] = None,
    engine: str = "event",
    oos_aggregation: str = "mean",
    id_attribute: str = "algorithm_id",
) -> List[Dict[str, Any]]:
    """Rank strategies by how well they held up out-of-sample.

    For every metric in *focus* (or *weights*), computes a "held-up
    ratio" per out-of-sample study — how much of the baseline
    (in-sample) value each OOS study retained, oriented so higher
    always means "held up better" regardless of whether the metric
    itself favours higher or lower raw values (e.g. ``max_drawdown``).
    Those ratios are aggregated across OOS studies (mean or
    worst-case min) and combined into a single ``robustness_score``
    using the focus/weights' relative importance (their magnitude;
    direction is already baked into the ratio).

    Args:
        backtests: ``Backtest`` objects, each expected to carry every
            study in ``studies`` (plus ``baseline_study``) on the same
            bundle.
        studies: Out-of-sample study names (or ``Study`` objects) to
            evaluate, e.g. ``["time_oos_param_sweep",
            "universe_oos_param_sweep"]``. Must not include
            ``baseline_study``.
        baseline_study: The in-sample study name (or ``Study``) used
            as the reference the OOS studies are measured against.
        focus: A :class:`BacktestEvaluationFocus` (or its string name)
            supplying metric weights, mirroring ``rank_index``.
        weights: Optional ``{metric: weight}`` overrides layered on
            top of ``focus``.
        engine: Which engine slot to read metrics from (default
            ``"event"``, since OOS validation is normally run there).
        oos_aggregation: How to combine a metric's held-up ratios
            across multiple OOS studies — ``"mean"`` (default,
            rewards overall retention) or ``"min"`` (worst-case,
            punishes any single bad regime hardest).
        id_attribute: Backtest attribute used to identify each row.

    Returns:
        List[Dict]: one dict per backtest with ``id_attribute``,
        ``robustness_score`` (``None`` if nothing could be computed)
        and ``held_up_ratios`` (the per-metric aggregated ratio, for
        inspection/debugging). Sorted by ``robustness_score``
        descending, with ``None`` scores last.
    """
    if oos_aggregation not in ("mean", "min"):
        raise ValueError(
            f"oos_aggregation must be 'mean' or 'min', got "
            f"{oos_aggregation!r}"
        )
    if not studies:
        raise ValueError(
            "studies must be a non-empty list of out-of-sample studies"
        )

    resolved_weights = _resolve_weights(focus, weights)
    if not resolved_weights:
        raise ValueError(
            "focus and/or weights produced no metrics to rank by"
        )

    study_names = [s.name if hasattr(s, "name") else s for s in studies]
    baseline_name = (
        baseline_study.name if hasattr(baseline_study, "name")
        else baseline_study
    )

    results = []
    for backtest in backtests:
        baseline_summary = _get_summary(backtest, engine, baseline_name)

        per_metric_scores = []
        held_up_ratios: Dict[str, float] = {}
        for metric, weight in resolved_weights.items():
            baseline_value = (
                getattr(baseline_summary, metric, None)
                if baseline_summary is not None else None
            )

            ratios = []
            for study_name in study_names:
                summary = _get_summary(backtest, engine, study_name)
                oos_value = (
                    getattr(summary, metric, None)
                    if summary is not None else None
                )
                ratio = _held_up_ratio(baseline_value, oos_value, weight)
                if ratio is not None:
                    ratios.append(ratio)

            if not ratios:
                continue

            aggregated = (
                min(ratios) if oos_aggregation == "min"
                else sum(ratios) / len(ratios)
            )
            held_up_ratios[metric] = aggregated
            per_metric_scores.append((aggregated, abs(weight)))

        if per_metric_scores:
            total_weight = sum(w for _, w in per_metric_scores)
            score = (
                sum(r * w for r, w in per_metric_scores) / total_weight
                if total_weight > 0 else None
            )
        else:
            score = None

        results.append({
            id_attribute: getattr(backtest, id_attribute, None) or "N/A",
            "robustness_score": score,
            "held_up_ratios": held_up_ratios,
        })

    results.sort(
        key=lambda r: (
            r["robustness_score"] is None, -(r["robustness_score"] or 0)
        )
    )
    return results
