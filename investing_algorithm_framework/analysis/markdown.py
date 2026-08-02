import math
from typing import Dict, List, Any, Union


def create_markdown_table(data: List[Union[Dict[str, Any], Any]]):
    """
    Create a markdown table with evenly spaced columns for nice display
    in notebook output cells.

    Args:
        data (List[dict] or List[object]): List of dictionaries or objects
            containing data.

    Returns:
        str: Markdown formatted table with evenly spaced columns.
    """
    if not data or len(data) == 0:
        return ("| No Data Available |\n"
                "|-------------------|\n"
                "| No records found  |\n")

    # Determine if data contains dicts or objects
    is_dict = isinstance(data[0], dict)

    # Get columns from data
    if is_dict:
        columns = list(data[0].keys())
    else:
        # For objects, get all attributes (excluding private ones)
        columns = [
            attr for attr in dir(data[0])
            if not attr.startswith('_')
            and not callable(getattr(data[0], attr))
        ]

    # Generate header titles
    header_titles = [col.replace("_", " ").title() for col in columns]

    # Collect and format all row data
    all_rows_data = []
    for item in data:
        row_values = []
        for col in columns:
            # Get value
            if is_dict:
                value = item.get(col)
            else:
                value = getattr(item, col, None)

            # Format value
            if value is None:
                formatted_value = "N/A"
            elif isinstance(value, float):
                formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)

            row_values.append(formatted_value)
        all_rows_data.append(row_values)

    # Calculate column widths based on both headers and data
    col_widths = []
    for i, header in enumerate(header_titles):
        max_width = len(header)
        for row in all_rows_data:
            if i < len(row):
                max_width = max(max_width, len(row[i]))
        col_widths.append(max_width)

    # Build markdown table
    markdown = ""

    # Header with padding
    header_parts = [
        title.ljust(width)
        for title, width in zip(header_titles, col_widths)
    ]
    markdown += "| " + " | ".join(header_parts) + " |\n"

    # Separator
    separator_parts = ["-" * width for width in col_widths]
    markdown += "| " + " | ".join(separator_parts) + " |\n"

    # Data rows
    for row_values in all_rows_data:
        row_parts = [
            value.ljust(width)
            for value, width in zip(row_values, col_widths)
        ]
        markdown += "| " + " | ".join(row_parts) + " |\n"

    return markdown


# Default key metrics shown by ``create_backtest_metrics_table``.
# Each entry is (summary_attribute, column_header, format_spec).
# ``format_spec`` is a Python format string applied to non-None values;
# use ``""`` to fall back to ``str()`` (useful for ints).
DEFAULT_METRIC_COLUMNS = [
    ("total_net_gain_percentage", "Net Gain %",   "{:.2f}"),
    ("cagr",                      "CAGR %",       "{:.2f}"),
    ("sharpe_ratio",              "Sharpe",       "{:.2f}"),
    ("sortino_ratio",             "Sortino",      "{:.2f}"),
    ("calmar_ratio",              "Calmar",       "{:.2f}"),
    ("profit_factor",             "Profit Factor", "{:.2f}"),
    ("max_drawdown",              "Max DD %",     "{:.2f}"),
    ("annual_volatility",         "Volatility %", "{:.2f}"),
    ("win_rate",                  "Win Rate %",   "{:.2f}"),
    ("number_of_trades",          "Trades",       ""),
    ("stability_score", "Stability",     "{:.2f}"),
    ("consistency_score", "Consistency",   "{:.2f}"),
]


# Attribute names that the framework stores as decimal ratios
# (e.g. ``0.25`` for 25 %) but which don't follow the ``_percentage``
# naming convention. The metric-table renderer rescales these by 100
# alongside any ``*_percentage`` field so that columns labelled "%"
# render in the same human-readable unit across per-run and summary
# rows.
_PERCENT_RATIO_ATTRS = {
    "cagr",
    "max_drawdown",
    "win_rate",
    "annual_volatility",
}


DEFAULT_SUMMARY_METRIC_COLUMNS = [
    ("total_net_gain_percentage", "Net Gain %",   "{:.2f}"),
    ("cagr",                      "CAGR %",       "{:.2f}"),
    ("sharpe_ratio",              "Sharpe",       "{:.2f}"),
    ("sortino_ratio",             "Sortino",      "{:.2f}"),
    ("calmar_ratio",              "Calmar",       "{:.2f}"),
    ("profit_factor",             "Profit Factor", "{:.2f}"),
    ("max_drawdown",              "Max DD %",     "{:.2f}"),
    ("annual_volatility",         "Volatility %", "{:.2f}"),
    ("win_rate",                  "Win Rate %",   "{:.2f}"),
    ("number_of_trades",          "Trades",       ""),
    ("stability_score",           "Stability",     "{:.2f}"),
    ("consistency_score",         "Consistency",   "{:.2f}"),
    ("number_of_windows",              "Windows",      ""),
    ("average_window_duration (days)",             "Avg Window Duration (days)", "{:.2f}"),
]

# Default trade-focused metrics shown by
# ``create_trade_metrics_table``. All attributes exist on both
# ``BacktestMetrics`` (per-run) and ``BacktestSummaryMetrics``
# (per-engine aggregate), so this list works for either ``level``.
DEFAULT_TRADE_METRIC_COLUMNS = [
    ("number_of_trades",                 "Trades",        ""),
    ("number_of_trades_closed",          "Closed",        ""),
    ("win_rate",                         "Win Rate",      "{:.2f}"),
    ("profit_factor",                    "Profit Factor", "{:.2f}"),
    ("average_trade_gain_percentage",    "Avg Win %",     "{:.2f}"),
    ("average_trade_loss_percentage",    "Avg Loss %",    "{:.2f}"),
    ("average_trade_return_percentage",  "Avg Return %",  "{:.2f}"),
    ("average_trade_duration",           "Avg Duration",  "{:.2f}"),
    ("trades_per_week",                  "Trades/Week",   "{:.2f}"),
]

DEFAULT_METRIC_COLUMNS = [
    ("total_net_gain_percentage", "Net Gain %",   "{:.2f}"),
    ("cagr",                      "CAGR %",       "{:.2f}"),
    ("sharpe_ratio",              "Sharpe",       "{:.2f}"),
    ("sortino_ratio",             "Sortino",      "{:.2f}"),
    ("calmar_ratio",              "Calmar",       "{:.2f}"),
    ("profit_factor",             "Profit Factor", "{:.2f}"),
    ("max_drawdown",              "Max DD %",     "{:.2f}"),
    ("annual_volatility",         "Volatility %", "{:.2f}"),
    ("win_rate",                  "Win Rate %",   "{:.2f}"),
    ("number_of_trades",          "Trades",       ""),
    ("number_of_windows",              "Windows",      ""),
    ("average_window_duration (days)",             "Avg Window Duration (days)", "{:.2f}"),
]


def create_backtest_metrics_table(
    backtests: List[Any],
    engine: str = "vector",
    level: str = "summary",
    window: Any = None,
    metrics: List = None,
    id_attribute: str = "algorithm_id",
    sort_by: str = None,
    descending: bool = True,
    study: str = None,
    row_offset: int = 0,
    row_limit: int = None,
) -> str:
    """Build a markdown table of key headline metrics for a list of
    backtests, scoped to a single engine (``"vector"`` or ``"event"``).

    A ``Backtest`` exposes two distinct metric layers per engine:

    * **Per-run metrics** — one ``BacktestMetrics`` instance per
      window in a rolling backtest, attached to each
      ``BacktestRun``. Use ``level="run"`` to get one row per
      ``(backtest, window)`` pair, with a ``"Window"`` column
      identifying the run.
    * **Summary metrics** — a single ``BacktestSummaryMetrics``
      aggregating across all runs for the engine, returned by
      ``backtest.get_summary(engine)``. This is the default
      (``level="summary"``), giving one row per backtest.

    Most column names (``sharpe_ratio``, ``cagr``, ``max_drawdown`` …)
    exist on both metric types so the default ``metrics`` list works
    for both levels.

    Args:
        backtests: List of ``Backtest`` objects (as returned by
            ``run_vector_backtests`` / ``LocalDirStore.open`` etc.).
        engine: Which engine slot to read metrics from. One of
            ``"vector"`` (default) or ``"event"``. Backtests that have
            no run in the requested slot are silently skipped.
        level: ``"summary"`` (default) for one aggregated row per
            backtest, or ``"run"`` for one row per rolling-window run.
        window: Optional run filter, only meaningful when
            ``level="run"``. Accepts any of:

            * a string — matched against
              ``run.backtest_date_range_name``;
            * a ``BacktestDateRange`` — matched by
              ``(start_date, end_date)`` (and by ``name`` when set);
            * a list/tuple of either of the above — a run is kept
              when it matches *any* entry.

            Runs that don't match are skipped. Ignored when
            ``level="summary"``.
        metrics: Optional override of the columns. Either a list of
            attribute names (strings) or a list of
            ``(attribute, header, format_spec)`` tuples. Defaults to
            ``DEFAULT_METRIC_COLUMNS``.
        id_attribute: Backtest attribute used as the first column to
            identify each row. Defaults to ``"algorithm_id"``.
        sort_by: Optional metric attribute name to sort rows by.
            Rows with ``None`` for that attribute are placed last.
        descending: Sort direction when ``sort_by`` is set.
        study: Optional study name to scope the lookup to a specific
            study slot in a multi-study bundle. Forwarded to
            ``backtest.get_summary(engine, study=...)`` /
            ``backtest.get_runs(engine, study=...)``. When omitted, the
            framework's default-study rule applies (single-study
            bundles resolve automatically; multi-study bundles raise
            ``OperationalException`` and require an explicit value).
        row_offset: Number of sorted result rows to skip. Defaults to 0.
        row_limit: Optional maximum number of sorted result rows to render.

    Returns:
        str: A markdown-formatted table. Falls back to the
        no-data placeholder when nothing matches the engine slot.
    """
    if engine not in ("vector", "event"):
        raise ValueError(
            f"engine must be 'vector' or 'event', got {engine!r}"
        )
    if level not in ("summary", "run"):
        raise ValueError(
            f"level must be 'summary' or 'run', got {level!r}"
        )
    if row_offset < 0:
        raise ValueError("row_offset must be >= 0")
    if row_limit is not None and row_limit <= 0:
        raise ValueError("row_limit must be > 0 when provided")
    if window is not None and level != "run":
        # Silently ignored at summary level — warn the caller instead
        # so misuse is visible without breaking notebooks.
        import warnings
        warnings.warn(
            "`window` is only meaningful when level='run'; ignoring.",
            stacklevel=2,
        )

    # Normalise the optional window filter into a list of matchers.
    window_filters = _normalise_window_filter(window) \
        if (window is not None and level == "run") else None

    # Normalise the column spec.
    if metrics is None:
        columns = DEFAULT_METRIC_COLUMNS
        if level == "run":
            # ``stability_score`` / ``consistency_score`` are
            # cross-window aggregates that only exist on the summary
            # metrics; drop them from per-run tables where they would
            # always render as ``N/A``.
            columns = [
                col for col in columns
                if col[0] not in ("stability_score", "consistency_score")
            ]
    else:
        columns = []
        for entry in metrics:
            if isinstance(entry, str):
                columns.append((entry, entry.replace("_", " ").title(), ""))
            else:
                # Allow 2- or 3-tuples; pad missing format with "".
                attr = entry[0]
                header = entry[1] if len(entry) > 1 else attr
                fmt = entry[2] if len(entry) > 2 else ""
                columns.append((attr, header, fmt))

    # Collect (backtest, metrics_obj, window_label) triples for the
    # requested engine. ``window_label`` is None for summary level.
    triples = []
    for backtest in backtests:
        engines = backtest.engines() if hasattr(backtest, "engines") else []
        if engine not in engines:
            continue

        if level == "summary":
            summary = _get_summary(backtest, engine, study)
            if summary is None:
                continue
            triples.append((backtest, summary, None))
        else:  # level == "run"
            runs = _get_runs(backtest, engine, study)
            for run in runs:
                if window_filters is not None \
                        and not _run_matches_any(run, window_filters):
                    continue
                run_metrics = getattr(run, "backtest_metrics", None)
                if run_metrics is None:
                    continue
                backtest_window = getattr(run, "backtest_window", None)
                window_label = (
                    getattr(backtest_window, "name", None)
                    or getattr(run, "backtest_date_range_name", None)
                    or _format_window_dates(run)
                    or "—"
                )
                triples.append((backtest, run_metrics, window_label))

    if not triples:
        return create_markdown_table([])

    # Optional sort by a metric attribute (``None`` placed last).
    if sort_by is not None:
        def _has_value(triple):
            return getattr(triple[1], sort_by, None) is not None

        def _sort_key(triple):
            return getattr(triple[1], sort_by, None)

        with_value = [t for t in triples if _has_value(t)]
        without_value = [t for t in triples if not _has_value(t)]
        with_value.sort(key=_sort_key, reverse=descending)
        triples = with_value + without_value

    triples = triples[row_offset:]
    if row_limit is not None:
        triples = triples[:row_limit]

    # Build row dicts so we can reuse ``create_markdown_table``.
    id_header = id_attribute.replace("_", " ").title()
    rows = []
    for backtest, metrics_obj, window_label in triples:
        row = {
            id_header: getattr(backtest, id_attribute, None) or "N/A",
            "Engine": engine,
        }
        if level == "run":
            row["Window"] = window_label
        for attr, header, fmt in columns:
            value = getattr(metrics_obj, attr, None)
            # The framework stores percentage fields as decimals
            # (e.g. 0.25 == 25%). For display in columns labelled "%"
            # we multiply by 100 so per-run and summary rows render in
            # a consistent, human-readable unit. Attributes ending in
            # ``_percentage`` are rescaled automatically; additional
            # well-known decimal ratios (cagr, max_drawdown, win_rate,
            # volatility) are listed in ``_PERCENT_RATIO_ATTRS``.
            if value is not None \
                    and (attr.endswith("_percentage")
                         or attr in _PERCENT_RATIO_ATTRS) \
                    and isinstance(value, (int, float)) \
                    and not isinstance(value, bool):
                value = value * 100
            if value is None:
                row[header] = "N/A"
            elif fmt:
                try:
                    row[header] = fmt.format(value)
                except (TypeError, ValueError):
                    row[header] = str(value)
            else:
                row[header] = str(value)
        rows.append(row)

    return create_markdown_table(rows)


def create_trade_metrics_table(
    backtests: List[Any],
    engine: str = "vector",
    level: str = "summary",
    window: Any = None,
    metrics: List = None,
    id_attribute: str = "algorithm_id",
    sort_by: str = None,
    descending: bool = True,
    study: str = None,
) -> str:
    """Build a markdown table of trade-focused metrics for a list of
    backtests.

    Thin wrapper around :func:`create_backtest_metrics_table` that
    defaults the column set to :data:`DEFAULT_TRADE_METRIC_COLUMNS`
    (trade counts, win rate, profit factor, average win/loss/return,
    average duration, trade frequency). All other arguments behave
    identically — see :func:`create_backtest_metrics_table` for full
    semantics of ``engine``, ``level``, ``window``, ``id_attribute``,
    ``sort_by``, ``descending`` and ``study``.

    Args:
        backtests: List of ``Backtest`` objects.
        engine: ``"vector"`` (default) or ``"event"``.
        level: ``"summary"`` (default) or ``"run"``.
        window: Optional run filter, only meaningful when
            ``level="run"``.
        metrics: Optional column override. Defaults to
            :data:`DEFAULT_TRADE_METRIC_COLUMNS`. Same format as
            :func:`create_backtest_metrics_table` — either attribute
            names (strings) or ``(attribute, header, format_spec)``
            tuples.
        id_attribute: Backtest attribute used as the first column.
        sort_by: Optional metric attribute name to sort rows by.
        descending: Sort direction when ``sort_by`` is set.
        study: Optional study name to scope multi-study bundles.

    Returns:
        str: A markdown-formatted table.
    """
    return create_backtest_metrics_table(
        backtests=backtests,
        engine=engine,
        level=level,
        window=window,
        metrics=metrics if metrics is not None
        else DEFAULT_TRADE_METRIC_COLUMNS,
        id_attribute=id_attribute,
        sort_by=sort_by,
        descending=descending,
        study=study,
    )


def create_cross_study_metrics_table(
    backtests: List[Any],
    studies: List[Any],
    engine: str = "event",
    metric: str = "sharpe_ratio",
    metric_header: str = None,
    fmt: str = "{:.2f}",
    id_attribute: str = "algorithm_id",
    baseline_study: Any = None,
    sort_by: Any = None,
    descending: bool = True,
) -> str:
    """Compare one metric for the same strategies across studies.

    ``create_backtest_metrics_table`` gives one row per *(backtest,
    study)* pair when called once per study; this instead lays the
    same strategies out side-by-side, one row per backtest and one
    column per study, so you can read off at a glance whether an
    in-sample winner's edge held up in each out-of-sample regime.

    Args:
        backtests: List of ``Backtest`` objects, each expected to
            carry every study in ``studies`` on the same bundle (the
            standard multi-study-per-envelope layout produced by
            ``app.run_backtest(..., study=..., backtest_storage_directory=...)``
            when the study names match across runs).
        studies: Study names (or ``Study`` objects — ``.name`` is
            used) to compare, in column order, e.g.
            ``["in_sample_param_sweep", "time_oos_param_sweep",
            "universe_oos_param_sweep"]``.
        engine: Which engine slot to read ``metric`` from, ``"vector"``
            or ``"event"`` (default ``"event"``).
        metric: The ``BacktestSummaryMetrics`` attribute to compare
            (default ``"sharpe_ratio"``).
        metric_header: Optional column-name label. Defaults to
            ``metric`` title-cased.
        fmt: Format spec applied to each value.
        id_attribute: Backtest attribute used as the first column.
        baseline_study: Optional study name (from ``studies``) to
            treat as the reference regime. When set, an extra
            ``"<study> vs <baseline> %"`` column is added per
            non-baseline study: ``100 * value / baseline_value``. A
            value under 100% means the metric degraded relative to
            the baseline — for metrics where *lower* is better (e.g.
            ``max_drawdown``), read this the other way round.
        sort_by: Optional study name (from ``studies``) to sort rows
            by that study's metric column. Rows with no value for
            that study are placed last.
        descending: Sort direction when ``sort_by`` is set.

    Returns:
        str: A markdown-formatted table, one row per backtest.
    """
    if engine not in ("vector", "event"):
        raise ValueError(
            f"engine must be 'vector' or 'event', got {engine!r}"
        )
    if not studies:
        raise ValueError("studies must be a non-empty list")

    study_names = [s.name if hasattr(s, "name") else s for s in studies]
    header = metric_header or metric.replace("_", " ").title()
    is_percent = (
        metric.endswith("_percentage") or metric in _PERCENT_RATIO_ATTRS
    )
    id_header = id_attribute.replace("_", " ").title()

    entries = []
    for backtest in backtests:
        raw_values = {}
        for study_name in study_names:
            summary = _get_summary(backtest, engine, study_name)
            raw_values[study_name] = (
                getattr(summary, metric, None) if summary is not None
                else None
            )

        row = {id_header: getattr(backtest, id_attribute, None) or "N/A"}
        for study_name in study_names:
            value = raw_values[study_name]
            display = (
                value * 100 if (value is not None and is_percent) else value
            )
            col = f"{study_name} {header}"
            if display is None:
                row[col] = "N/A"
            else:
                try:
                    row[col] = fmt.format(display)
                except (TypeError, ValueError):
                    row[col] = str(display)

        if baseline_study is not None and baseline_study in raw_values:
            baseline_value = raw_values[baseline_study]
            for study_name in study_names:
                if study_name == baseline_study:
                    continue
                value = raw_values[study_name]
                col = f"{study_name} vs {baseline_study} %"
                if value is None or not baseline_value:
                    row[col] = "N/A"
                else:
                    row[col] = "{:.0f}%".format(100 * value / baseline_value)

        entries.append((row, raw_values))

    if sort_by is not None:
        if sort_by not in study_names:
            raise ValueError(
                f"sort_by must be one of {study_names!r}, got {sort_by!r}"
            )

        def _has_value(entry):
            return entry[1][sort_by] is not None

        def _sort_key(entry):
            return entry[1][sort_by]

        with_value = [e for e in entries if _has_value(e)]
        without_value = [e for e in entries if not _has_value(e)]
        with_value.sort(key=_sort_key, reverse=descending)
        entries = with_value + without_value

    return create_markdown_table([row for row, _ in entries])


def _get_summary(backtest: Any, engine: str, study: Any) -> Any:
    """Resolve a backtest's per-engine summary, optionally scoped to
    a study.

    Forwards ``study`` only when explicitly provided to keep
    compatibility with older ``Backtest`` shapes that may not accept
    the keyword. Returns ``None`` when the slot is missing.
    """
    if not hasattr(backtest, "get_summary"):
        return None
    if study is None:
        return backtest.get_summary(engine)
    return backtest.get_summary(engine, study=study)


def _get_runs(backtest: Any, engine: str, study: Any) -> List[Any]:
    """Resolve a backtest's per-engine runs, optionally scoped to a
    study. Returns ``[]`` when the slot is missing.
    """
    if not hasattr(backtest, "get_runs"):
        return []
    if study is None:
        return backtest.get_runs(engine) or []
    return backtest.get_runs(engine, study=study) or []


def _format_window_dates(run: Any) -> str:
    """Fallback window label built from a run's start/end dates."""
    start = getattr(run, "backtest_start_date", None)
    end = getattr(run, "backtest_end_date", None)
    if start is None or end is None:
        return ""
    fmt = "%Y-%m-%d"
    try:
        return f"{start.strftime(fmt)} → {end.strftime(fmt)}"
    except AttributeError:
        return f"{start} → {end}"


def _normalise_window_filter(window: Any) -> List[Any]:
    """Return ``window`` as a list, accepting scalar or iterable input.

    A bare string or ``BacktestDateRange`` is wrapped in a single-item
    list; an existing list/tuple is returned as a list copy.
    """
    if isinstance(window, (list, tuple)):
        return list(window)
    return [window]


def _run_matches_any(run: Any, filters: List[Any]) -> bool:
    """True when ``run`` matches at least one entry in ``filters``."""
    return any(_run_matches(run, f) for f in filters)


def _run_matches(run: Any, window: Any) -> bool:
    """Match a ``BacktestRun`` against a string name or a
    ``BacktestDateRange``.

    For strings: compares case-insensitively against the run's
    ``backtest_date_range_name``.

    For ``BacktestWindow``: matches the parent window name (the stable key
    generated as ``window_N``) or the complete train/test range pair.

    For ``BacktestDateRange``: a match requires both the start and end
    dates to equal the run's start/end. If the range also carries a
    ``name``, that name alone is treated as a sufficient match
    (handy when only the name is known).
    """
    run_name = getattr(run, "backtest_date_range_name", None)
    run_start = getattr(run, "backtest_start_date", None)
    run_end = getattr(run, "backtest_end_date", None)
    run_window = getattr(run, "backtest_window", None)

    if isinstance(window, str):
        parent_name = getattr(run_window, "name", None)
        return (
            (run_name is not None
             and str(run_name).lower() == window.lower())
            or (parent_name is not None
                and str(parent_name).lower() == window.lower())
        )

    # Duck-type a ``BacktestWindow`` before ``BacktestDateRange``. Runs
    # execute one active range, but retain the parent window so callers can
    # select ``window_N`` regardless of whether the study ran train or test.
    window_train = getattr(window, "train_range", None)
    if window_train is not None:
        window_name = getattr(window, "name", None)
        run_window_name = getattr(run_window, "name", None)
        if window_name and run_window_name:
            return str(window_name).lower() == str(run_window_name).lower()
        return (
            getattr(run_window, "train_range", None) == window_train
            and getattr(run_window, "test_range", None)
            == getattr(window, "test_range", None)
        )

    # Duck-type a ``BacktestDateRange`` — avoids a hard import cycle.
    range_name = getattr(window, "name", None)
    range_start = getattr(window, "start_date", None)
    range_end = getattr(window, "end_date", None)

    if range_name and run_name \
            and str(range_name).lower() == str(run_name).lower():
        return True

    if range_start is not None and range_end is not None:
        return run_start == range_start and run_end == range_end

    return False


def show_study(study) -> str:
    """Render a Study as a markdown summary for notebook display.

    Returns the markdown string and, when running in IPython/Jupyter,
    automatically displays it as rendered HTML.
    """
    lines = [f"## Study: {study.name}"]

    if study.description:
        lines.append(f"_{study.description}_")
    lines.append("")

    # Config table
    config_rows = []
    if study.initial_capital is not None:
        config_rows.append(("Initial Capital", f"{study.initial_capital:,.2f}"))
    if study.risk_free_rate is not None:
        config_rows.append(("Risk-Free Rate", f"{study.risk_free_rate:.4f}"))
    if study.sample_type is not None:
        config_rows.append(("Sample Type", str(study.sample_type)))
    window_part = getattr(study, "window_part", None)
    window_part_str = (
        window_part.value if hasattr(window_part, "value") else window_part
    ) or "test"
    config_rows.append(("Window Part", window_part_str))
    if study.engines:
        config_rows.append((
            "Engines", ", ".join(str(e) for e in study.engines)
        ))

    if config_rows:
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")
        for label, value in config_rows:
            lines.append(f"| {label} | {value} |")
        lines.append("")

    # Universe
    universe = getattr(study, "universe", None)
    if universe is not None:
        lines.append("### Universe")
        lines.append("")
        lines.append(f"- **Market:** {universe.market}")
        lines.append(
            f"- **Symbols:** {', '.join(universe.symbols)}"
        )
        if universe.trading_symbol:
            lines.append(
                f"- **Trading Symbol:** {universe.trading_symbol}"
            )
        lines.append("")

    # Backtest windows
    windows = getattr(study, "backtest_windows", None)
    if windows:
        lines.append("### Backtest Windows")
        lines.append(
            f"_Window part: **{window_part_str}** — determines which "
            "range(s) below are actually executed._"
        )
        lines.append("")
        win_data = []
        for w in windows:
            train = getattr(w, "train_range", None)
            test = getattr(w, "test_range", None)

            if window_part_str == "train":
                runs_label = "Train" if train else "—"
            elif window_part_str == "both":
                parts = [
                    label for label, rng in (("Train", train), ("Test", test))
                    if rng
                ]
                runs_label = " + ".join(parts) if parts else "—"
            else:  # "test" (default) — falls back to train_range
                runs_label = "Test" if test else ("Train" if train else "—")

            row = {
                "Name": getattr(w, "name", None) or "—",
                "Runs": runs_label,
            }
            if train:
                row["Train"] = (
                    f"{train.start_date:%Y-%m-%d} → "
                    f"{train.end_date:%Y-%m-%d}"
                )
            if test:
                row["Test"] = (
                    f"{test.start_date:%Y-%m-%d} → "
                    f"{test.end_date:%Y-%m-%d}"
                )
            win_data.append(row)
        lines.append(create_markdown_table(win_data))

    md = "\n".join(lines)

    try:
        from IPython.display import Markdown, display
        display(Markdown(md))
    except ImportError:
        pass

    return md


def show_trade_insights(
    backtest,
    study_name: str = None,
    window_name: str = None,
    engine: str = "vector",
) -> str:
    """Render trade-level insights for one or more backtests as markdown.

    Shows headline metrics, per-symbol trade breakdown, and a
    trade list for the matched run(s).
    """
    backtests = (
        list(backtest)
        if isinstance(backtest, (list, tuple))
        else [backtest]
    )
    runs = [
        run
        for result in backtests
        for run in _get_runs(result, engine, study_name)
    ]

    if window_name is not None:
        runs = [
            r for r in runs
            if getattr(r.backtest_window, "name", None) == window_name
        ]

    if not runs:
        md = "_No matching runs found._"
        try:
            from IPython.display import Markdown, display
            display(Markdown(md))
        except ImportError:
            pass
        return md

    def format_number(value, decimals=2, signed=False):
        if value is None:
            return "N/A"
        numeric = float(value)
        if math.isnan(numeric):
            return "N/A"
        if math.isinf(numeric):
            return "∞" if numeric > 0 else "-∞"
        sign = "+" if signed else ""
        return f"{numeric:{sign},.{decimals}f}"

    def format_decimal_percent(value, signed=False):
        if value is None:
            return "N/A"
        return f"{format_number(float(value) * 100, signed=signed)}%"

    def format_percentage_points(value):
        if value is None:
            return "N/A"
        return f"{format_number(value)}%"

    def append_metric_table(rows):
        lines.append("| Metric | Value |")
        lines.append("|:-------|------:|")
        for label, value in rows:
            lines.append(f"| {label} | {value} |")
        lines.append("")

    lines = ["## Trade Insights", ""]
    if study_name:
        lines.append(f"- **Study:** {study_name}")
    if window_name:
        lines.append(f"- **Window:** {window_name}")
    lines.append("")

    for run in runs:
        window = run.backtest_window
        w_label = getattr(window, "name", None) or (
            f"{run.backtest_start_date:%Y-%m-%d} → "
            f"{run.backtest_end_date:%Y-%m-%d}"
        )

        if len(runs) > 1:
            lines.append(f"### Window: {w_label}")
            lines.append("")

        # All aggregate values come from this run's persisted metrics.
        m = run.backtest_metrics
        if m is not None:
            lines.append("### Backtest Run Metrics")
            lines.append("")
            append_metric_table([
                ("Initial Capital", format_number(m.initial_unallocated)),
                ("Final Portfolio Value", format_number(m.final_value)),
                ("Net P&L", format_number(m.total_net_gain, signed=True)),
                ("Total Return", format_decimal_percent(
                    m.total_net_gain_percentage, signed=True
                )),
                ("CAGR", format_decimal_percent(m.cagr, signed=True)),
            ])

            lines.append("### Risk & Return")
            lines.append("")
            append_metric_table([
                ("Sharpe Ratio", format_number(m.sharpe_ratio)),
                ("Sortino Ratio", format_number(m.sortino_ratio)),
                ("Calmar Ratio", format_number(m.calmar_ratio)),
                ("Profit Factor", format_number(m.profit_factor)),
                ("Annual Volatility", format_decimal_percent(
                    m.annual_volatility
                )),
                ("Maximum Drawdown", format_decimal_percent(
                    m.max_drawdown
                )),
            ])

            lines.append("### Trade Statistics")
            lines.append("")
            append_metric_table([
                ("Total Trades", f"{m.number_of_trades:,}"),
                ("Closed Trades", f"{m.number_of_trades_closed:,}"),
                ("Open at End", f"{m.number_of_trades_open_at_end:,}"),
                ("Long Trades", f"{m.number_of_long_trades:,}"),
                ("Long Record", (
                    f"{m.number_of_winning_long_trades:,} wins / "
                    f"{m.number_of_losing_long_trades:,} losses "
                    f"({m.number_of_long_trades_closed:,} closed)"
                )),
                ("Long Win Rate", format_decimal_percent(m.long_win_rate)),
                ("Short Trades", f"{m.number_of_short_trades:,}"),
                ("Short Record", (
                    f"{m.number_of_winning_short_trades:,} wins / "
                    f"{m.number_of_losing_short_trades:,} losses "
                    f"({m.number_of_short_trades_closed:,} closed)"
                )),
                ("Short Win Rate", format_decimal_percent(m.short_win_rate)),
                ("Winning Trades", (
                    f"{m.number_of_positive_trades:,} "
                    f"({format_percentage_points(m.percentage_positive_trades)})"
                )),
                ("Losing Trades", (
                    f"{m.number_of_negative_trades:,} "
                    f"({format_percentage_points(m.percentage_negative_trades)})"
                )),
                ("Win Rate", format_decimal_percent(m.win_rate)),
                ("Average Winner", format_decimal_percent(
                    m.average_trade_gain_percentage, signed=True
                )),
                ("Average Loser", format_decimal_percent(
                    m.average_trade_loss_percentage, signed=True
                )),
                ("Average Duration", (
                    f"{format_number(m.average_trade_duration, decimals=1)} hours"
                )),
                ("Trades per Week", format_number(m.trades_per_week)),
            ])

        # Per-symbol breakdown
        trades = run.trades
        if trades:
            symbols = sorted(set(t.target_symbol for t in trades))
            lines.append("### Per-Symbol Breakdown")
            lines.append("")
            sym_rows = []
            for sym in symbols:
                sym_trades = [t for t in trades if t.target_symbol == sym]
                closed = [
                    t for t in sym_trades
                    if str(t.status).lower() == "closed"
                ]
                wins = [t for t in closed if t.net_gain_absolute > 0]
                losses = [t for t in closed if t.net_gain_absolute < 0]
                total_pnl = sum(t.net_gain_absolute for t in closed)
                wr = (
                    len(wins) / len(closed) * 100 if closed else 0
                )
                sym_rows.append({
                    "Symbol": sym,
                    "Trades": len(sym_trades),
                    "Wins": len(wins),
                    "Losses": len(losses),
                    "Win Rate": f"{wr:.1f}%",
                    "Net P&L": format_number(total_pnl, signed=True),
                })
            lines.append(create_markdown_table(sym_rows))

            # Trade list
            lines.append("### Trade List")
            lines.append("")
            trade_rows = []
            for t in sorted(trades, key=lambda x: x.opened_at or 0):
                side = "SHORT" if getattr(t, "is_short", False) else "LONG"
                trade_rows.append({
                    "Symbol": t.target_symbol,
                    "Side": side,
                    "Status": t.status,
                    "Opened": (
                        f"{t.opened_at:%Y-%m-%d %H:%M}"
                        if t.opened_at else "—"
                    ),
                    "Closed": (
                        f"{t.closed_at:%Y-%m-%d %H:%M}"
                        if t.closed_at else "—"
                    ),
                    "Entry": (
                        format_number(t.open_price)
                        if t.open_price is not None else "—"
                    ),
                    "Net P&L": format_number(
                        t.net_gain_absolute, signed=True
                    ),
                    "Return": format_percentage_points(
                        t.net_gain_percentage
                    ),
                })
            lines.append(create_markdown_table(trade_rows))

    md = "\n".join(lines)

    try:
        from IPython.display import Markdown, display
        display(Markdown(md))
    except ImportError:
        pass

    return md


def _study_label(study: Any) -> str:
    """Render a study reference for display headers as just its name,
    avoiding the full ``Study`` dataclass repr when a ``Study``
    instance (rather than a plain name string) is passed in.
    """
    return getattr(study, "name", None) or str(study)


def _selection_label(selection: Any) -> str:
    """Render a scalar or collection of named filters for a heading."""
    if isinstance(selection, (list, tuple)):
        return ", ".join(_selection_label(item) for item in selection)
    return (
        selection if isinstance(selection, str)
        else (getattr(selection, "name", None) or str(selection))
    )


def show_backtest_summaries(
    backtests: List[Any],
    study: str = None,
    engine: str = "vector",
    columns: List = None,
    id_attribute: str = "algorithm_id",
    sort_by: str = None,
    descending: bool = True,
) -> str:
    """Render one summary row per backtest as markdown for notebook
    display.

    Thin, display-oriented wrapper around
    :func:`create_backtest_metrics_table` (``level="summary"``) that
    adds a heading and automatically renders the result as rendered
    HTML when running in IPython/Jupyter.

    Args:
        backtests: List of ``Backtest`` objects.
        study: Optional study name to scope the lookup to a specific
            study slot in a multi-study bundle. Forwarded to
            ``backtest.get_summary(engine, study=...)``. When omitted,
            the framework's default-study rule applies.
        engine: ``"vector"`` (default) or ``"event"``.
        columns: Optional column override — a list of attribute
            names (strings) or ``(attribute, header, format_spec)``
            tuples. Defaults to :data:`DEFAULT_METRIC_COLUMNS`.
        id_attribute: Backtest attribute used as the first column.
        sort_by: Optional metric attribute name to sort rows by.
        descending: Sort direction when ``sort_by`` is set.

    Returns:
        str: The rendered markdown string.
    """
    table = create_backtest_metrics_table(
        backtests=backtests,
        engine=engine,
        level="summary",
        metrics=columns,
        id_attribute=id_attribute,
        sort_by=sort_by,
        descending=descending,
        study=study,
    )

    heading = "## Backtest Summaries"
    if study:
        heading += f" {_study_label(study)}"
    lines = [heading, ""]
    lines.append(f"- **Engine:** {engine}")
    lines.append("")
    lines.append(table)

    md = "\n".join(lines)

    try:
        from IPython.display import Markdown, display
        display(Markdown(md))
    except ImportError:
        pass

    return md


def show_backtest_runs(
    backtests: List[Any],
    study: str = None,
    run: Any = None,
    engine: str = "vector",
    columns: List = None,
    id_attribute: str = "algorithm_id",
    sort_by: str = None,
    descending: bool = True,
    page: int = 1,
    page_size: int = 25,
) -> str:
    """Render one row per rolling-window run as markdown for notebook
    display.

    Thin, display-oriented wrapper around
    :func:`create_backtest_metrics_table` (``level="run"``) that adds
    a heading and automatically renders the result as rendered HTML
    when running in IPython/Jupyter.

    Args:
        backtests: List of ``Backtest`` objects.
        study: Optional study name to scope the lookup to a specific
            study slot in a multi-study bundle. Forwarded to
            ``backtest.get_runs(engine, study=...)``. When omitted,
            the framework's default-study rule applies.
        run: Optional run filter. Accepts any of:

            * a string — matched against
              ``run.backtest_date_range_name``;
            * a ``BacktestWindow`` — matched by its parent window name;
            * a ``BacktestDateRange`` — matched by
              ``(start_date, end_date)`` (and by ``name`` when set);
            * a list/tuple of either of the above — a run is kept
              when it matches *any* entry.

            When omitted, every run is shown.
        engine: ``"vector"`` (default) or ``"event"``.
        columns: Optional column override — a list of attribute
            names (strings) or ``(attribute, header, format_spec)``
            tuples. Defaults to :data:`DEFAULT_METRIC_COLUMNS`.
        id_attribute: Backtest attribute used as the first column.
        sort_by: Optional metric attribute name to sort rows by.
        descending: Sort direction when ``sort_by`` is set.
        page: One-based result page to render. Defaults to 1.
        page_size: Number of run rows per page. Defaults to 25.

    Returns:
        str: The rendered markdown string.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    total_rows = _count_matching_runs(backtests, engine, study, run)
    total_pages = max(1, math.ceil(total_rows / page_size))
    if page > total_pages:
        raise ValueError(
            f"page {page} exceeds the available {total_pages} page(s)"
        )

    table = create_backtest_metrics_table(
        backtests=backtests,
        engine=engine,
        level="run",
        window=run,
        metrics=columns,
        id_attribute=id_attribute,
        sort_by=sort_by,
        descending=descending,
        study=study,
        row_offset=(page - 1) * page_size,
        row_limit=page_size,
    )

    heading_parts = ["## Backtest Runs"]
    if study:
        heading_parts.append(_study_label(study))
    if run is not None:
        heading_parts.append(_selection_label(run))
    lines = [" ".join(heading_parts), ""]
    lines.append(f"- **Engine:** {engine}")
    lines.append(
        f"- **Page:** {page} of {total_pages} "
        f"({total_rows} runs; {page_size} per page)"
    )
    lines.append("")
    lines.append(table)

    md = "\n".join(lines)

    try:
        from IPython.display import Markdown, display
        display(Markdown(md))
    except ImportError:
        pass

    return md


def _count_matching_runs(
    backtests: List[Any],
    engine: str,
    study: Any,
    window: Any,
) -> int:
    """Count run rows using the same eligibility rules as the table."""
    window_filters = (
        _normalise_window_filter(window) if window is not None else None
    )
    count = 0
    for backtest in backtests:
        engines = backtest.engines() if hasattr(backtest, "engines") else []
        if engine not in engines:
            continue
        for backtest_run in _get_runs(backtest, engine, study):
            if window_filters is not None and not _run_matches_any(
                backtest_run, window_filters
            ):
                continue
            if getattr(backtest_run, "backtest_metrics", None) is not None:
                count += 1
    return count
