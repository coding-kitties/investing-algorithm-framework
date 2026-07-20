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
                window_label = (
                    getattr(run, "backtest_date_range_name", None)
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

    For ``BacktestDateRange``: a match requires both the start and end
    dates to equal the run's start/end. If the range also carries a
    ``name``, that name alone is treated as a sufficient match
    (handy when only the name is known).
    """
    run_name = getattr(run, "backtest_date_range_name", None)
    run_start = getattr(run, "backtest_start_date", None)
    run_end = getattr(run, "backtest_end_date", None)

    if isinstance(window, str):
        return (
            run_name is not None
            and str(run_name).lower() == window.lower()
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
