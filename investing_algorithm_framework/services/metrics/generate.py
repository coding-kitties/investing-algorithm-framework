from typing import List
from logging import getLogger

from investing_algorithm_framework.domain import BacktestMetrics, \
    BacktestRun, OperationalException, Backtest, BacktestDateRange
from .cagr import get_cagr
from .calmar_ratio import get_calmar_ratio
from .drawdown import get_drawdown_series, get_max_drawdown, \
    get_max_daily_drawdown, get_max_drawdown_absolute, \
    get_max_drawdown_duration
from .equity_curve import get_equity_curve
from .exposure import get_exposure_ratio, get_cumulative_exposure, \
    get_trades_per_year, get_trades_per_day
from .profit_factor import get_profit_factor, get_gross_loss, get_gross_profit
from .returns import get_monthly_returns, get_yearly_returns, \
    get_worst_year, get_best_year, get_best_month, get_worst_month, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_monthly_return, get_average_monthly_return_winning_months, \
    get_average_monthly_return_losing_months, get_cumulative_return, \
    get_cumulative_return_series
from .returns import get_total_return, get_final_value, get_total_loss, \
    get_total_growth
from .sharpe_ratio import get_sharpe_ratio, get_rolling_sharpe_ratio
from .sortino_ratio import get_sortino_ratio
from .volatility import get_annual_volatility
from .win_rate import get_win_rate, get_win_loss_ratio, get_current_win_rate, \
    get_current_win_loss_ratio
from .trades import get_average_trade_duration, get_average_trade_size, \
    get_number_of_trades, get_positive_trades, get_number_of_closed_trades, \
    get_negative_trades, get_average_trade_return, get_number_of_open_trades, \
    get_worst_trade, get_best_trade, get_average_trade_gain, \
    get_average_trade_loss, get_median_trade_return, \
    get_current_average_trade_gain, get_current_average_trade_return, \
    get_current_average_trade_duration, get_current_average_trade_loss

logger = getLogger("investing_algorithm_framework")

def create_backtest_metrics_for_backtest(
    backtest: Backtest,
    risk_free_rate: float, metrics: List[str] = None,
    backtest_date_range: BacktestDateRange = None
) -> Backtest:

    """
    Create BacktestMetrics for a Backtest object.

    Args:
        backtest (Backtest): The Backtest object containing
            backtest runs.
        risk_free_rate (float): The risk-free rate used in certain
            metric calculations.
        metrics (List[str], optional): List of metric names to compute.
            If None, a default set of metrics will be computed.
        backtest_date_range (BacktestDateRange, optional): The date range
            for the backtest. If None, all backtest metrics will be computed
            for each backtest run.

    Returns:
        Backtest: The Backtest object with computed metrics for each run.
    """
    if backtest_date_range is not None:
        backtest_runs = [
            backtest.get_backtest_run(backtest_date_range)
        ]
    else:
        backtest_runs = backtest.get_all_backtest_runs()

    for backtest_run in backtest_runs:
        # If a date range is provided, check if the backtest run falls
        # within the range
        backtest_metrics = create_backtest_metrics(
            backtest_run, risk_free_rate, metrics
        )
        backtest_run.backtest_metrics = backtest_metrics

    backtest.backtest_runs = backtest_runs
    return backtest


def create_backtest_metrics(
    backtest_run: BacktestRun, risk_free_rate: float, metrics: List[str] = None
) -> BacktestMetrics:
    """
    Create a BacktestMetrics instance and optionally save it to a file.

    Args:
        backtest_run (BacktestRun): The BacktestRun object containing
            portfolio snapshots and trades.
        risk_free_rate (float): The risk-free rate used in certain
            metric calculations.
        metrics (List[str], optional): List of metric names to compute.
            If None, a default set of metrics will be computed.

    Returns:
        BacktestMetrics: The computed backtest metrics.
    """

    if metrics is None:
        metrics = [
            "backtest_start_date",
            "backtest_end_date",
            "equity_curve",
            "final_value",
            "total_growth",
            "total_growth_percentage",
            "total_net_gain",
            "total_net_gain_percentage",
            "total_loss",
            "total_loss_percentage",
            "cumulative_return",
            "cumulative_return_series",
            "cagr",
            "sharpe_ratio",
            "rolling_sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "profit_factor",
            "annual_volatility",
            "monthly_returns",
            "yearly_returns",
            "drawdown_series",
            "max_drawdown",
            "max_drawdown_absolute",
            "max_daily_drawdown",
            "max_drawdown_duration",
            "trades_per_year",
            "trade_per_day",
            "exposure_ratio",
            "cumulative_exposure",
            "best_trade",
            "worst_trade",
            "number_of_positive_trades",
            "percentage_positive_trades",
            "number_of_negative_trades",
            "percentage_negative_trades",
            "average_trade_duration",
            "average_trade_size",
            "average_trade_loss",
            "average_trade_loss_percentage",
            "average_trade_gain",
            "average_trade_gain_percentage",
            "average_trade_return",
            "average_trade_return_percentage",
            "median_trade_return",
            "number_of_trades",
            "number_of_trades_closed",
            "number_of_trades_opened",
            "number_of_trades_open_at_end",
            "win_rate",
            "current_win_rate",
            "win_loss_ratio",
            "current_win_loss_ratio",
            "percentage_winning_months",
            "percentage_winning_years",
            "average_monthly_return",
            "average_monthly_return_losing_months",
            "average_monthly_return_winning_months",
            "best_month",
            "best_year",
            "worst_month",
            "worst_year",
            "total_number_of_days",
            "current_average_trade_gain",
            "current_average_trade_return",
            "current_average_trade_duration",
            "current_average_trade_loss",
        ]

    backtest_metrics = BacktestMetrics(
        backtest_start_date=backtest_run.backtest_start_date,
        backtest_end_date=backtest_run.backtest_end_date,
    )

    def safe_set(metric_name, func, *args, index=None):
        if metric_name in metrics:
            try:
                value = func(*args)
                if index is not None and isinstance(value, (list, tuple)):
                    setattr(backtest_metrics, metric_name, value[index])
                else:
                    setattr(backtest_metrics, metric_name, value)
            except OperationalException as e:
                logger.warning(f"{metric_name} failed: {e}")

    # Grouped metrics needing special handling
    if "total_net_gain" in metrics or "total_net_gain_percentage" in metrics:
        try:
            total_return = get_total_return(backtest_run.portfolio_snapshots)
            if "total_net_gain" in metrics:
                backtest_metrics.total_net_gain = total_return[0]
            if "total_net_gain_percentage" in metrics:
                backtest_metrics.total_net_gain_percentage = total_return[1]
        except OperationalException as e:
            logger.warning(f"total_return failed: {e}")

    if "total_growth" in metrics or "total_growth_percentage" in metrics:
        try:
            total_growth = get_total_growth(backtest_run.portfolio_snapshots)
            if "total_growth" in metrics:
                backtest_metrics.total_growth = total_growth[0]
            if "total_growth_percentage" in metrics:
                backtest_metrics.total_growth_percentage = total_growth[1]
        except OperationalException as e:
            logger.warning(f"total_growth failed: {e}")

    if "total_loss" in metrics or "total_loss_percentage" in metrics:
        try:
            total_loss = get_total_loss(backtest_run.portfolio_snapshots)
            if "total_loss" in metrics:
                backtest_metrics.total_loss = total_loss[0]
            if "total_loss_percentage" in metrics:
                backtest_metrics.total_loss_percentage = total_loss[1]
        except OperationalException as e:
            logger.warning(f"total_loss failed: {e}")

    if ("average_trade_return" in metrics
            or "average_trade_return_percentage" in metrics):
        try:
            avg_return = get_average_trade_return(backtest_run.trades)
            if "average_trade_return" in metrics:
                backtest_metrics.average_trade_return = avg_return[0]
            if "average_trade_return_percentage" in metrics:
                backtest_metrics.average_trade_return_percentage = \
                    avg_return[1]
        except OperationalException as e:
            logger.warning(f"average_trade_return failed: {e}")

    if ("average_trade_gain" in metrics
            or "average_trade_gain_percentage" in metrics):
        try:
            avg_gain = get_average_trade_gain(backtest_run.trades)
            if "average_trade_gain" in metrics:
                backtest_metrics.average_trade_gain = avg_gain[0]
            if "average_trade_gain_percentage" in metrics:
                backtest_metrics.average_trade_gain_percentage = avg_gain[1]
        except OperationalException as e:
            logger.warning(f"average_trade_gain failed: {e}")

    if ("average_trade_loss" in metrics
            or "average_trade_loss_percentage" in metrics):
        try:
            avg_loss = get_average_trade_loss(backtest_run.trades)
            if "average_trade_loss" in metrics:
                backtest_metrics.average_trade_loss = avg_loss[0]
            if "average_trade_loss_percentage" in metrics:
                backtest_metrics.average_trade_loss_percentage = avg_loss[1]
        except OperationalException as e:
            logger.warning(f"average_trade_loss failed: {e}")

    if ("current_average_trade_gain" in metrics
            or "get_current_average_trade_gain_percentage" in metrics):
        try:
            current_avg_gain = get_current_average_trade_gain(
                backtest_run.trades
            )

            if "current_average_trade_gain" in metrics:
                backtest_metrics.current_average_trade_gain = \
                    current_avg_gain[0]

            if "current_average_trade_gain_percentage" in metrics:
                backtest_metrics.current_average_trade_gain_percentage = \
                    current_avg_gain[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_gain failed: {e}")

    if ("current_average_trade_return" in metrics
            or "current_average_trade_return_percentage" in metrics):
        try:
            current_avg_return = get_current_average_trade_return(
                backtest_run.trades
            )

            if "current_average_trade_return" in metrics:
                backtest_metrics.current_average_trade_return = \
                    current_avg_return[0]
            if "current_average_trade_return_percentage" in metrics:
                backtest_metrics.current_average_trade_return_percentage =\
                    current_avg_return[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_return failed: {e}")

    if "current_average_trade_duration" in metrics:
        try:
            current_avg_duration = get_current_average_trade_duration(
                backtest_run.trades, backtest_run
            )
            backtest_metrics.current_average_trade_duration = \
                current_avg_duration
        except OperationalException as e:
            logger.warning(f"current_average_trade_duration failed: {e}")

    if ("current_average_trade_loss" in metrics
            or "current_average_trade_loss_percentage" in metrics):
        try:
            current_avg_loss = get_current_average_trade_loss(
                backtest_run.trades
            )
            if "current_average_trade_loss" in metrics:
                backtest_metrics.current_average_trade_loss = \
                    current_avg_loss[0]
            if "current_average_trade_loss_percentage" in metrics:
                backtest_metrics.current_average_trade_loss_percentage = \
                    current_avg_loss[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_loss failed: {e}")

    safe_set("number_of_positive_trades", get_positive_trades, backtest_run.trades)
    safe_set("percentage_positive_trades", get_positive_trades, backtest_run.trades, index=1)
    safe_set("number_of_negative_trades", get_negative_trades, backtest_run.trades)
    safe_set("percentage_negative_trades", get_negative_trades, backtest_run.trades, index=1)
    safe_set("median_trade_return", get_median_trade_return, backtest_run.trades, index=0)
    safe_set("median_trade_return_percentage", get_median_trade_return, backtest_run.trades, index=1)
    safe_set("number_of_trades", get_number_of_trades, backtest_run.trades)
    safe_set("number_of_trades_closed", get_number_of_closed_trades, backtest_run.trades)
    safe_set("number_of_trades_opened", get_number_of_open_trades, backtest_run.trades)
    safe_set("average_trade_duration", get_average_trade_duration, backtest_run.trades)
    safe_set("average_trade_size", get_average_trade_size, backtest_run.trades)
    safe_set("equity_curve", get_equity_curve, backtest_run.portfolio_snapshots)
    safe_set("final_value", get_final_value, backtest_run.portfolio_snapshots)
    safe_set("cagr", get_cagr, backtest_run.portfolio_snapshots)
    safe_set("sharpe_ratio", get_sharpe_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("rolling_sharpe_ratio", get_rolling_sharpe_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("sortino_ratio", get_sortino_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("profit_factor", get_profit_factor, backtest_run.trades)
    safe_set("calmar_ratio", get_calmar_ratio, backtest_run.portfolio_snapshots)
    safe_set("annual_volatility", get_annual_volatility, backtest_run.portfolio_snapshots)
    safe_set("monthly_returns", get_monthly_returns, backtest_run.portfolio_snapshots)
    safe_set("yearly_returns", get_yearly_returns, backtest_run.portfolio_snapshots)
    safe_set("drawdown_series", get_drawdown_series, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown", get_max_drawdown, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown_absolute", get_max_drawdown_absolute, backtest_run.portfolio_snapshots)
    safe_set("max_daily_drawdown", get_max_daily_drawdown, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown_duration", get_max_drawdown_duration, backtest_run.portfolio_snapshots)
    safe_set("trades_per_year", get_trades_per_year, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("trades_per_day", get_trades_per_day, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("exposure_ratio", get_exposure_ratio, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("cumulative_exposure", get_cumulative_exposure, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("best_trade", get_best_trade, backtest_run.trades)
    safe_set("worst_trade", get_worst_trade, backtest_run.trades)
    safe_set("win_rate", get_win_rate, backtest_run.trades)
    safe_set("current_win_rate", get_current_win_rate, backtest_run.trades)
    safe_set("win_loss_ratio", get_win_loss_ratio, backtest_run.trades)
    safe_set("current_win_loss_ratio", get_current_win_loss_ratio, backtest_run.trades)
    safe_set("percentage_winning_months", get_percentage_winning_months, backtest_run.portfolio_snapshots)
    safe_set("percentage_winning_years", get_percentage_winning_years, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return", get_average_monthly_return, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return_winning_months", get_average_monthly_return_winning_months, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return_losing_months", get_average_monthly_return_losing_months, backtest_run.portfolio_snapshots)
    safe_set("best_month", get_best_month, backtest_run.portfolio_snapshots)
    safe_set("best_year", get_best_year, backtest_run.portfolio_snapshots)
    safe_set("worst_month", get_worst_month, backtest_run.portfolio_snapshots)
    safe_set("worst_year", get_worst_year, backtest_run.portfolio_snapshots)
    safe_set("gross_loss", get_gross_loss, backtest_run.trades)
    safe_set("gross_profit", get_gross_profit, backtest_run.trades)
    safe_set("cumulative_return_series", get_cumulative_return_series, backtest_run.portfolio_snapshots)
    safe_set("cumulative_return", get_cumulative_return, backtest_run.portfolio_snapshots)
    return backtest_metrics
