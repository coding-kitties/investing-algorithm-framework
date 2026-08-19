from .analysis import generate_rolling_backtest_windows, \
    generate_anchored_backtest_windows, \
    generate_k_fold_backtest_windows, \
    rank_results, create_weights, \
    get_missing_timeseries_data_entries, fill_missing_timeseries_data, \
    create_markdown_table, create_backtest_metrics_table, \
    create_trade_metrics_table, print_bundle_summary, \
    show_study, show_trade_insights, \
    show_backtest_summaries, show_backtest_runs, \
    DEFAULT_TRADE_METRIC_COLUMNS, \
    analyze_backtest_windows, \
    plot_backtest_windows, plot_window_correlation_matrix, \
    load_top_selection, TopSelection, \
    create_cross_study_metrics_table, \
    rank_by_cross_study_robustness  # noqa: F401
from .app import App, Algorithm, \
    TradingStrategy, StatelessAction, Task, AppHook, Context, \
    add_html_report, BacktestReport, \
    pretty_print_trades, pretty_print_positions, \
    pretty_print_orders, pretty_print_backtest, \
    get_equity_curve_with_drawdown_chart, \
    get_rolling_sharpe_ratio_chart, get_monthly_returns_heatmap_chart, \
    get_yearly_returns_bar_chart, get_entry_and_exit_signals, \
    get_ohlcv_data_completeness_chart, get_equity_curve_chart
from .domain import ApiException, combine_backtests, Study, \
    combine_multi_universe_backtest, PositionSize, BacktestWindow, \
    OrderType, OperationalException, OrderStatus, OrderSide, tqdm, \
    TimeUnit, TimeInterval, Order, Portfolio, Backtest, DataError, \
    Position, TimeFrame, INDEX_DATETIME, MarketCredential, TakeProfitRule, \
    PortfolioConfiguration, RESOURCE_DIRECTORY, AWS_LAMBDA_LOGGING_CONFIG, \
    Trade, APP_MODE, AppMode, DATETIME_FORMAT, load_backtests_from_directory, \
    BacktestDateRange, convert_polars_to_pandas, BacktestRun, Universe, \
    DEFAULT_LOGGING_CONFIG, DataType, DataProvider, StopLossRule, \
    ScalingRule, TradingCost, BacktestEngine, \
    CooldownRule, CooldownTrigger, CooldownBlocks, CooldownTracker, \
    TradeStatus, generate_backtest_summary_metrics, generate_algorithm_id, \
    APPLICATION_DIRECTORY, DataSource, OrderExecutor, PortfolioProvider, \
    SnapshotInterval, AWS_S3_STATE_BUCKET_NAME, BacktestEvaluationFocus, \
    save_backtests_to_directory, BacktestMetrics, DATA_DIRECTORY, \
    retag_backtests, migrate_backtests, \
    Blotter, DefaultBlotter, SimulationBlotter, Transaction, \
    SlippageModel, NoSlippage, PercentageSlippage, FixedSlippage, \
    VolumeImpactSlippage, VolumeShareSlippage, FixedBasisPointsSlippage, \
    CommissionModel, NoCommission, PercentageCommission, FixedCommission, \
    FillModel, FullFill, VolumeBasedFill, \
    FXRateProvider, StaticFXRateProvider, \
    ScheduledDeposit, SyncResult, PortfolioOutOfSyncError, \
    DateRule, TimeRule, Schedule, ScheduledFunction, \
    Signal, SignalSide, SignalSeries, \
    signals_from_column, signal_series_from_column, signals_from_panel, \
    ConflictPolicy, ConflictResolution  # noqa: F401
from .domain import Pipeline, Factor, CustomFactor, Filter, \
    AverageDollarVolume, AverageTradedValue, CrossSectionalMean, \
    Neutralize, Returns, RollingBeta, RSI, SMA, StaticPerSymbol, \
    Volatility, BacktestIndex, BUNDLE_FORMAT_VERSION, \
    ExecutionConfig, StudySampleType, WindowPart  # noqa: F401
from .infrastructure import AzureBlobStorageStateHandler, \
    CSVOHLCVDataProvider, CSVTickerDataProvider, CSVURLDataProvider, \
    JSONURLDataProvider, ParquetURLDataProvider, \
    CCXTOHLCVDataProvider, CCXTTickerDataProvider, \
    PandasOHLCVDataProvider, OHLCVDataProviderBase, \
    YahooOHLCVDataProvider, \
    AlphaVantageOHLCVDataProvider, PolygonOHLCVDataProvider, \
    AWSS3StorageStateHandler
from .create_app import create_app
from .cli.index_command import build_index, rank_index, format_table, \
    prune_backtests, promote_backtests
from .domain.backtesting.bundle import remove_study_from_bundle
from .services.backtest_store import LocalDirStore
from .download_data import download, download_v2, DownloadResult, \
    create_data_storage_path
from .services.executors import (
    Executor, LimitOrderExecutor, MarketOrderExecutor,
)
from .services import (
    get_annual_volatility,
    get_sortino_ratio,
    get_drawdown_series,
    get_max_drawdown,
    get_equity_curve,
    get_price_efficiency_ratio,
    get_sharpe_ratio,
    get_profit_factor,
    get_cumulative_profit_factor_series,
    get_rolling_profit_factor_series,
    get_cagr,
    get_standard_deviation_returns,
    get_standard_deviation_downside_returns,
    get_max_drawdown_absolute,
    get_total_return,
    get_exposure_ratio,
    get_average_trade_duration,
    get_win_rate,
    get_win_loss_ratio,
    get_calmar_ratio,
    get_trade_frequency,
    get_yearly_returns,
    get_monthly_returns,
    get_best_year,
    get_best_month,
    get_worst_year,
    get_worst_month,
    get_best_trade,
    get_worst_trade,
    get_average_yearly_return,
    get_average_trade_gain,
    get_average_trade_loss,
    get_average_monthly_return,
    get_percentage_winning_months,
    get_max_drawdown_duration,
    get_max_daily_drawdown,
    get_trades_per_day,
    get_trades_per_year,
    get_average_monthly_return_losing_months,
    get_average_monthly_return_winning_months,
    get_percentage_winning_years,
    get_rolling_sharpe_ratio,
    create_backtest_metrics,
    get_total_growth,
    get_total_loss,
    get_cumulative_exposure,
    get_median_trade_return,
    get_average_trade_return,
    get_risk_free_rate_us,
    get_cumulative_return,
    get_cumulative_return_series,
    get_current_average_trade_return,
    get_current_average_trade_gain,
    get_current_average_trade_duration,
    get_current_average_trade_loss,
    get_negative_trades,
    get_positive_trades,
    get_number_of_trades,
    get_current_win_rate,
    get_current_win_loss_ratio,
    create_backtest_metrics_for_backtest,
    recalculate_backtests,
    recalculate_backtests_in_directory,
    get_omega_ratio,
    get_ulcer_index,
    get_trade_mae_mfe_statistics,
    TradeTakeProfitService,
    TradeStopLossService,
)
try:
    from .notebook.magic import load_ipython_extension  # noqa: F401
except ImportError:
    # IPython is an optional dependency (install with
    # `pip install investing-algorithm-framework[notebook]`) — don't
    # let its absence break importing the framework itself.
    def load_ipython_extension(ipython):  # pragma: no cover
        raise ImportError(
            "IPython is required to use the %backtest magic. Install "
            "it with `pip install investing-algorithm-framework"
            "[notebook]`."
        )


__all__ = [
    "Algorithm",
    "RESOURCE_DIRECTORY",
    "App",
    "AppHook",
    "create_app",
    "ApiException",
    "OrderType",
    "OrderStatus",
    "OrderSide",
    "PortfolioConfiguration",
    "TimeUnit",
    "DateRule",
    "TimeRule",
    "Schedule",
    "ScheduledFunction",
    "Signal",
    "SignalSide",
    "SignalSeries",
    "signals_from_column",
    "signals_from_panel",
    "signal_series_from_column",
    "ConflictPolicy",
    "ConflictResolution",
    "Executor",
    "LimitOrderExecutor",
    "MarketOrderExecutor",
    "TimeInterval",
    "TradingStrategy",
    "Order",
    "Portfolio",
    "Position",
    "StatelessAction",
    "Task",
    "pretty_print_backtest",
    "INDEX_DATETIME",
    "Trade",
    "TimeFrame",
    "MarketCredential",
    "OperationalException",
    "APP_MODE",
    "AppMode",
    "DATETIME_FORMAT",
    "Backtest",
    "Universe",
    "BacktestDateRange",
    "convert_polars_to_pandas",
    "AzureBlobStorageStateHandler",
    "DEFAULT_LOGGING_CONFIG",
    "BacktestReport",
    "TradeStatus",
    "Context",
    "APPLICATION_DIRECTORY",
    "download",
    "pretty_print_orders",
    "pretty_print_trades",
    "pretty_print_positions",
    "DataSource",
    "OrderExecutor",
    "PortfolioProvider",
    "SnapshotInterval",
    "add_html_report",
    "AWSS3StorageStateHandler",
    "AWS_S3_STATE_BUCKET_NAME",
    "AWS_LAMBDA_LOGGING_CONFIG",
    'DataType',
    'CSVOHLCVDataProvider',
    'CSVTickerDataProvider',
    'CSVURLDataProvider', 'JSONURLDataProvider',
    'ParquetURLDataProvider', "CCXTOHLCVDataProvider",
    "CCXTTickerDataProvider",
    "OHLCVDataProviderBase",
    "YahooOHLCVDataProvider",
    "AlphaVantageOHLCVDataProvider",
    "PolygonOHLCVDataProvider",
    "DataProvider",
    "get_annual_volatility",
    "get_sortino_ratio",
    "get_drawdown_series",
    "get_max_drawdown",
    "get_equity_curve",
    "get_price_efficiency_ratio",
    "get_sharpe_ratio",
    "get_profit_factor",
    "get_cumulative_profit_factor_series",
    "get_rolling_profit_factor_series",
    "get_sharpe_ratio",
    "get_cagr",
    "get_standard_deviation_returns",
    "get_standard_deviation_downside_returns",
    "get_max_drawdown_absolute",
    "get_total_return",
    "get_exposure_ratio",
    "get_cumulative_exposure",
    "get_average_trade_duration",
    "get_win_rate",
    "get_win_loss_ratio",
    "get_calmar_ratio",
    "get_trade_frequency",
    "get_yearly_returns",
    "get_monthly_returns",
    "get_best_year",
    "get_best_month",
    "get_worst_year",
    "get_worst_month",
    "get_best_trade",
    "get_worst_trade",
    "get_average_yearly_return",
    "get_average_trade_gain",
    "get_average_trade_loss",
    "get_average_monthly_return",
    "get_percentage_winning_months",
    "get_average_trade_duration",
    "get_trade_frequency",
    "get_win_rate",
    "get_win_loss_ratio",
    "get_calmar_ratio",
    "get_max_drawdown_absolute",
    "get_max_drawdown_duration",
    "get_max_daily_drawdown",
    "get_trades_per_day",
    "get_trades_per_year",
    "get_average_monthly_return_losing_months",
    "get_average_monthly_return_winning_months",
    "get_percentage_winning_years",
    "get_rolling_sharpe_ratio",
    "create_backtest_metrics",
    "PandasOHLCVDataProvider",
    "get_equity_curve_with_drawdown_chart",
    "get_rolling_sharpe_ratio_chart",
    "get_monthly_returns_heatmap_chart",
    "get_yearly_returns_bar_chart",
    "get_ohlcv_data_completeness_chart",
    "rank_results",
    "create_weights",
    "get_entry_and_exit_signals",
    "BacktestEvaluationFocus",
    "combine_backtests",
    "combine_multi_universe_backtest",
    "PositionSize",
    "get_median_trade_return",
    "get_average_trade_return",
    "get_risk_free_rate_us",
    "get_cumulative_return",
    "get_cumulative_return_series",
    "get_total_loss",
    "get_total_growth",
    "generate_backtest_summary_metrics",
    "get_equity_curve_chart",
    "get_current_win_rate",
    "get_current_win_loss_ratio",
    "get_current_average_trade_loss",
    "get_current_average_trade_duration",
    "get_current_average_trade_gain",
    "get_current_average_trade_return",
    "get_negative_trades",
    "get_positive_trades",
    "get_number_of_trades",
    "BacktestRun",
    "load_backtests_from_directory",
    "save_backtests_to_directory",
    "retag_backtests",
    "migrate_backtests",
    "DataError",
    "create_backtest_metrics_for_backtest",
    "recalculate_backtests",
    "recalculate_backtests_in_directory",
    "get_omega_ratio",
    "get_ulcer_index",
    "get_trade_mae_mfe_statistics",
    "TakeProfitRule",
    "StopLossRule",
    "ScalingRule",
    "CooldownRule",
    "CooldownTrigger",
    "CooldownBlocks",
    "CooldownTracker",
    "TradingCost",
    "TradeStopLossService",
    "TradeTakeProfitService",
    "generate_algorithm_id",
    "BacktestMetrics",
    "generate_rolling_backtest_windows",
    "generate_anchored_backtest_windows",
    "generate_k_fold_backtest_windows",
    "tqdm",
    "get_missing_timeseries_data_entries",
    "fill_missing_timeseries_data",
    "create_markdown_table",
    "create_backtest_metrics_table",
    "create_trade_metrics_table",
    "show_study",
    "show_backtest_summaries",
    "show_backtest_runs",
    "DEFAULT_TRADE_METRIC_COLUMNS",
    "show_trade_insights",
    "print_bundle_summary",
    "load_top_selection",
    "TopSelection",
    "create_cross_study_metrics_table",
    "rank_by_cross_study_robustness",
    "build_index",
    "rank_index",
    "format_table",
    "prune_backtests",
    "promote_backtests",
    "remove_study_from_bundle",
    "LocalDirStore",
    "download_v2",
    "DownloadResult",
    "create_data_storage_path",
    "DATA_DIRECTORY",
    "Blotter",
    "DefaultBlotter",
    "SimulationBlotter",
    "Transaction",
    "SlippageModel",
    "NoSlippage",
    "PercentageSlippage",
    "FixedSlippage",
    "VolumeImpactSlippage",
    "VolumeShareSlippage",
    "FixedBasisPointsSlippage",
    "CommissionModel",
    "NoCommission",
    "PercentageCommission",
    "FixedCommission",
    "FillModel",
    "FullFill",
    "VolumeBasedFill",
    "FXRateProvider",
    "StaticFXRateProvider",
    "BacktestIndex",
    "BUNDLE_FORMAT_VERSION",
    "Pipeline",
    "Factor",
    "CustomFactor",
    "Filter",
    "AverageDollarVolume",
    "AverageTradedValue",
    "CrossSectionalMean",
    "Neutralize",
    "Returns",
    "RollingBeta",
    "RSI",
    "SMA",
    "StaticPerSymbol",
    "Volatility",
    "load_ipython_extension",
    "Study",
    "ExecutionConfig",
    "WindowPart",
    "BacktestWindow",
    "StudySampleType",
    "ScheduledDeposit",
    "SyncResult",
    "PortfolioOutOfSyncError"
]
