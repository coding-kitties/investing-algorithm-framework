import logging
import math
from typing import List, Optional

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
    the compounded return is: (1 + 0.10) * (1 + 0.05) - 1 = 0.155 = 15.5%
    NOT simply 0.10 + 0.05 = 0.15.

    The framework consistently represents percentages as **decimals**
    (e.g. ``0.10`` for 10%), so this helper expects decimal inputs and
    returns a decimal. See issue #511 (B5) — earlier versions assumed
    whole-number percentages, which silently produced results off by a
    factor of ~100 once multi-window aggregation was exercised.

    Args:
        percentages (List[float | None]): List of period returns expressed
            as decimals (e.g. ``0.10`` for 10%).

    Returns:
        float | None: The compounded return as a decimal, or ``None`` if
            no valid percentages.
    """
    valid_percentages = [p for p in percentages if p is not None]
    if not valid_percentages:
        return None

    compounded = 1.0
    for pct in valid_percentages:
        compounded *= (1 + pct)

    return compounded - 1


def combine_backtests(backtests):
    """
    Combine multiple backtests into a single backtest by aggregating
    their results.

    Runs and per-engine summaries are combined per engine
    (vector with vector, event with event), matching the v9.0
    dual-engine model (see ``docs/architecture/backtest/v9.0-dual-engine-design.md``).

    Args:
        backtests (List[Backtest]): List of Backtest instances to combine.

    Returns:
        Backtest: A new Backtest instance representing the combined results.
    """
    from .backtest import Backtest, ENGINE_VECTOR, ENGINE_EVENT

    algorithm_id = None
    # v5: lineage pointer; must agree across every input bundle.
    # ``None`` ride-alongs from un-stamped inputs are tolerated; an
    # explicit mismatch is an error (you can't combine a primary
    # bundle with a sibling bundle pointing to a different anchor).
    anchor_algorithm_id: Optional[str] = None
    anchor_seen = False
    vector_runs = []
    event_runs = []

    # Determine the active study name *before* collecting runs so we can
    # scope get_runs() to the correct study slot. This is essential when
    # a bundle contains multiple studies (e.g. in-sample + OOS) and we
    # are merging windows within one specific study: without the scope,
    # get_runs() raises OperationalException("Backtest has N studies —
    # pass study= to disambiguate").
    _combine_study_name: Optional[str] = None
    for _bt in backtests:
        _ds = _bt.get_study() if hasattr(_bt, "get_study") else None
        _sn = _ds.name if _ds else None
        if _sn is not None:
            _combine_study_name = _sn
            break

    for backtest in backtests:
        if algorithm_id is None:
            algorithm_id = backtest.algorithm_id
        elif algorithm_id != backtest.algorithm_id:
            raise ValueError(
                "All backtests must belong to the same algorithm id"
                "to be combined."
            )

        bt_anchor = getattr(backtest, "anchor_algorithm_id", None)
        if bt_anchor is not None:
            if not anchor_seen:
                anchor_algorithm_id = bt_anchor
                anchor_seen = True
            elif anchor_algorithm_id != bt_anchor:
                raise ValueError(
                    "All backtests must share the same "
                    "anchor_algorithm_id to be combined "
                    f"(got {anchor_algorithm_id!r} and {bt_anchor!r})."
                )

        vector_runs += list(backtest.get_runs(ENGINE_VECTOR, study=_combine_study_name))
        event_runs += list(backtest.get_runs(ENGINE_EVENT, study=_combine_study_name))

    def _summary(runs):
        per_run_metrics = [
            r.backtest_metrics for r in runs
            if r.backtest_metrics is not None
        ]
        if not per_run_metrics:
            return None
        return generate_backtest_summary_metrics(per_run_metrics)

    vector_summary = _summary(vector_runs)
    event_summary = _summary(event_runs)

    metadata = None
    risk_free_rate = None

    # Check if there are duplicate backtest runs (per engine).
    for engine_runs, engine_label in (
        (vector_runs, ENGINE_VECTOR), (event_runs, ENGINE_EVENT),
    ):
        seen = set()
        for run in engine_runs:
            key = (run.backtest_start_date, run.backtest_end_date)
            if key in seen:
                logger.warning(
                    f"Duplicate {engine_label} backtest run detected for "
                    f"date range: {key} when combining backtests."
                )
            seen.add(key)

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

    # Phase 3b/3c: preserve the study identity across the combine.
    # When all inputs share the same ``study_name`` (the typical
    # multi-window case), the combined backtest stays in that study
    # slot — otherwise the post-combine save would silently demote it
    # back to the unnamed ``default`` study and merge-on-save would
    # then split runs across two studies on disk.
    study_name = None
    study_description = None
    for backtest in backtests:
        _ds = backtest.get_study() if hasattr(backtest, 'get_study') else None
        sn = _ds.name if _ds else None
        if sn is not None:
            study_name = sn
            break
    for backtest in backtests:
        _ds = backtest.get_study() if hasattr(backtest, 'get_study') else None
        sd = _ds.description if _ds else None
        if sd is not None:
            study_description = sd
            break

    # Preserve any additional study slots present on the inputs.
    # Rule 1 of the v5 merge contract (disjoint studies preserved
    # verbatim, same-name engine slots merged) is applied here
    # in-memory so the combined backtest can be saved through any of
    # the existing writers without losing studies.
    additional_studies: dict = {}
    for backtest in backtests:
        for name, study in (
            getattr(backtest, "studies", None) or {}
        ).items():
            if name == (study_name or "default"):
                # Same name as the legacy slot — its data already
                # lives on the combined ``vector_runs`` / ``event_runs``.
                continue
            if name in additional_studies:
                # Same-name conflict across inputs: keep the first
                # one we saw (callers can post-process if they need
                # different semantics).
                continue
            additional_studies[name] = study

    universes = []
    seen_universe_keys: set = set()
    for backtest in backtests:
        for u in (getattr(backtest, "universes", None) or []):
            key = getattr(u, "key", None)
            if key in seen_universe_keys:
                continue
            seen_universe_keys.add(key)
            universes.append(u)

    bt = Backtest(
        algorithm_id=algorithm_id,
        anchor_algorithm_id=anchor_algorithm_id,
        vector_runs=vector_runs,
        vector_summary=vector_summary,
        event_runs=event_runs,
        event_summary=event_summary,
        metadata=metadata,
        risk_free_rate=risk_free_rate,
        parameters=parameters,
        study_name=study_name,
        study_description=study_description,
        universes=universes,
    )
    for name, study in additional_studies.items():
        bt._studies[name] = study
    return bt


def combine_multi_universe_backtest(
    backtests_by_universe,
    universes=None,
    study_name=None,
    study_description=None,
):
    """Merge several per-universe Backtest bundles into one v4
    multi-universe envelope.

    Each input bundle is assumed to be the result of running the same
    strategy configuration (same algorithm_id / parameters) against
    one universe. This helper:

    * Stamps run.metadata['universe_key'] on every run of every input
      bundle with the corresponding universe key (overwriting any
      existing tag).
    * Concatenates runs into a single Backtest via combine_backtests.
    * Populates the universes catalogue on the result.
    * Rebuilds per-engine *_summaries_by_universe so each universe
      has its own roll-up alongside the pooled cross-universe summary.

    Args:
        backtests_by_universe: Mapping of universe_key to the Backtest
            produced for that universe.
        universes: Optional explicit list of Universe records to attach
            to the output. Keys must match backtests_by_universe. When
            omitted, a minimal set of Universe records is synthesized
            from each input bundle's Study.universe, falling back to
            the first run's data_sources[0]['market'] for market.
        study_name: Optional study label to stamp on the result.
        study_description: Optional study description.

    Returns:
        Backtest: A single Backtest whose runs are tagged by universe,
        with both pooled and per-universe summaries populated and ready
        for save_bundle.

    Raises:
        ValueError: If backtests_by_universe is empty or the inputs
            disagree on algorithm_id (via combine_backtests).
    """
    from .universe import Universe

    if not backtests_by_universe:
        raise ValueError(
            "combine_multi_universe_backtest requires at least one "
            "(universe_key, Backtest) entry."
        )

    # Tag every run with its universe key (overwrite to keep semantics
    # explicit: this is the canonical multi-universe merge path).
    ordered_keys = list(backtests_by_universe.keys())
    for key in ordered_keys:
        bt = backtests_by_universe[key]
        bt.tag_runs_universe(key, overwrite=True)

    merged = combine_backtests(
        [backtests_by_universe[k] for k in ordered_keys]
    )

    # Populate the universes catalogue. If the caller did not pass one,
    # synthesize a minimal record per key from the bundle's own Study
    # (symbols/trading_symbol live on Study.universe, not on runs) so
    # the catalogue is never silently empty.
    if universes is not None:
        merged.universes = [u for u in universes]
    else:
        synth: list = []
        for key in ordered_keys:
            bt = backtests_by_universe[key]
            study = bt.get_study()
            source_universe = study.universe if study is not None else None

            market = source_universe.market if source_universe else None
            if market is None:
                sample_run = None
                for engine in ("vector", "event"):
                    runs = bt.get_runs(engine)
                    if runs:
                        sample_run = runs[0]
                        break
                ds_list = getattr(sample_run, "data_sources", None) or []
                if ds_list and isinstance(ds_list[0], dict):
                    market = ds_list[0].get("market")

            synth.append(
                Universe(
                    key=key,
                    symbols=list(
                        source_universe.symbols if source_universe else []
                    ),
                    trading_symbol=(
                        source_universe.trading_symbol
                        if source_universe else None
                    ),
                    market=market,
                )
            )
        merged.universes = synth

    merged.regenerate_summaries_by_universe()

    if study_name is not None:
        _ds = merged.get_study()
        if _ds and _ds.name != study_name:
            merged.rename_study(_ds.name, study_name)
    if study_description is not None:
        _ds = merged.get_study()
        if _ds:
            _ds.description = study_description

    return merged


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
    # B1/B2 fix (issue #511): per-run ``total_loss`` is now the gross
    # loss magnitude, so the aggregate is simply the sum of per-run
    # ``total_loss`` (equivalent to ``sum(gross_loss)``). Both per-run
    # and aggregate use the same unit (positive currency).
    total_loss = sum(
        b.total_loss for b in valid_metrics
        if b.total_loss is not None
    )
    total_growth = sum(
        b.total_growth for b in valid_metrics
        if b.total_growth is not None
    )

    # === PERCENTAGE RETURNS ===
    # ``total_net_gain_percentage`` aggregates per-run returns into a
    # single bundle-level figure. We *cannot* compound the per-run
    # values via ``(1 + r1) * (1 + r2) * ...``: rolling backtest
    # windows commonly overlap (train_days > step_days), so chained
    # compounding double-counts the same calendar periods and inflates
    # the result by orders of magnitude (issue #511 follow-up).
    #
    # Instead we use the same definition as the per-run metric — net
    # PnL divided by capital deployed — but applied to the bundle:
    # ``sum(total_net_gain) / sum(initial_unallocated)``. This is
    # invariant to window overlap, agrees with the per-run formula,
    # and stays internally consistent with ``cagr`` (which is a
    # duration-weighted mean of per-run CAGRs).
    total_initial_capital = 0.0
    for b in valid_metrics:
        iv = getattr(b, "initial_unallocated", None)
        if isinstance(iv, (int, float)) and iv > 0:
            total_initial_capital += iv
    if total_initial_capital > 0 and total_net_gain is not None:
        total_net_gain_percentage = total_net_gain / total_initial_capital
    else:
        # Fall back to a duration-weighted mean of per-run percentages
        # when initial-capital figures are missing — still bounded and
        # never inflates with overlapping windows.
        total_net_gain_percentage = safe_weighted_mean(
            [b.total_net_gain_percentage for b in valid_metrics],
            [b.total_number_of_days for b in valid_metrics],
        )
    # ``total_loss`` is a non-multiplicative magnitude (it does not
    # compound across windows). Express the aggregate as the sum of
    # gross losses divided by the sum of initial capital across
    # windows, which keeps the unit (decimal fraction) consistent
    # with the per-run definition. See issue #511 (B2).
    total_initial_value = 0.0
    for b in valid_metrics:
        iv = getattr(b, "initial_unallocated", None)
        if isinstance(iv, (int, float)) and iv > 0:
            total_initial_value += iv
    if total_initial_value > 0 and total_loss is not None:
        total_loss_percentage = total_loss / total_initial_value
    else:
        total_loss_percentage = None
    # ``total_growth_percentage`` follows the same overlap-safe
    # definition as ``total_net_gain_percentage`` below: divide
    # aggregate growth by aggregate capital deployed instead of
    # compounding per-run percentages (which double-counts overlapping
    # rolling windows).
    if total_initial_value > 0 and total_growth is not None:
        total_growth_percentage = total_growth / total_initial_value
    else:
        total_growth_percentage = safe_weighted_mean(
            [b.total_growth_percentage for b in valid_metrics],
            [b.total_number_of_days for b in valid_metrics],
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
