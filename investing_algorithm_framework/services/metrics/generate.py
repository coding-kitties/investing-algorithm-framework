from typing import List

from investing_algorithm_framework.domain import BacktestMetrics, \
    TradeStatus, BacktestRun
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
    get_worst_trade, get_best_trade, get_worst_year, \
    get_best_year, get_best_month, get_worst_month, get_average_gain, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_loss, get_average_monthly_return, \
    get_average_monthly_return_winning_months, get_average_return, \
    get_average_monthly_return_losing_months, get_cumulative_return, \
    get_cumulative_return_series
from .returns import get_total_return, get_final_value, get_growth, \
    get_growth_percentage
from .sharpe_ratio import get_sharpe_ratio, get_rolling_sharpe_ratio
from .sortino_ratio import get_sortino_ratio
from .volatility import get_annual_volatility
from .win_rate import get_win_rate, get_win_loss_ratio


def create_backtest_metrics(
    backtest_run: BacktestRun, risk_free_rate: float, metrics: List[str] = None
) -> BacktestMetrics:
    """
    Create a BacktestMetrics instance and optionally save it to a file.
    """

    if metrics is None:
        metrics = [
            "equity_curve",
            "final_value",
            "total_net_gain",
            "total_net_gain_percentage",
            "cumulative_return",
            "cumulative_return_series",
            "cagr",
            "sharpe_ratio",
            "rolling_sharpe_ratio",
            "sortino_ratio",
            "profit_factor",
            "calmar_ratio",
            "annual_volatility",
            "monthly_returns",
            "yearly_returns",
            "drawdown_series",
            "max_drawdown",
            "max_drawdown_absolute",
            "max_daily_drawdown",
            "max_drawdown_duration",
            "trades_per_year",
            "trades_per_day",
            "exposure_ratio",
            "cumulative_exposure",
            "trades_average_gain",
            "trades_average_gain_percentage",
            "trades_average_loss",
            "trades_average_loss_percentage",
            "trades_average_return",
            "trades_average_return_percentage",
            "best_trade",
            "worst_trade",
            "average_trade_duration",
            "average_trade_size",
            "number_of_trades",
            "win_rate",
            "win_loss_ratio",
            "percentage_winning_months",
            "percentage_winning_years",
            "percentage_negative_trades",
            "percentage_positive_trades",
            "average_monthly_return",
            "average_monthly_return_winning_months",
            "average_monthly_return_losing_months",
            "best_month",
            "best_year",
            "worst_month",
            "worst_year",
            "gross_loss",
            "gross_profit",
            "growth",
            "growth_percentage"
        ]

    backtest_metrics = BacktestMetrics(
        backtest_start_date=backtest_run.backtest_start_date,
        backtest_end_date=backtest_run.backtest_end_date,
    )

    if "total_net_gain" in metrics or "total_net_gain_percentage" in metrics:
        total_return = get_total_return(backtest_run.portfolio_snapshots)

        if "total_net_gain" in metrics:
            backtest_metrics.total_net_gain = total_return[0]

        if "total_net_gain_percentage" in metrics:
            backtest_metrics.total_net_gain_percentage = total_return[1]

    if "trades_average_gain" in metrics \
            or "trades_average_gain_percentage" in metrics:
        trades_average_gain = get_average_gain(backtest_run.trades)

        if "trades_average_gain" in metrics:
            backtest_metrics.trades_average_gain = trades_average_gain[0]

        if "trades_average_gain_percentage" in metrics:
            backtest_metrics.trades_average_gain_percentage = \
                trades_average_gain[1]

    if "trades_average_loss" in metrics \
            or "trades_average_loss_percentage" in metrics:
        trades_average_loss = get_average_loss(
            backtest_run.trades
        )

        if "trades_average_loss" in metrics:
            backtest_metrics.trades_average_loss = trades_average_loss[0]

        if "trades_average_loss_percentage" in metrics:
            backtest_metrics.trades_average_loss_percentage = \
                trades_average_loss[1]

    number_of_negative_trades = 0.0
    number_of_positive_trades = 0.0
    number_of_trades_closed = 0
    number_of_trades_open = 0
    total_duration = 0
    total_trade_size = 0.0
    total_cost = 0.0
    trades = backtest_run.trades

    for trade in trades:
        total_cost += trade.cost
        total_duration += \
            ((trade.closed_at - trade.opened_at).total_seconds() /
                3600) if trade.closed_at else 0
        total_trade_size += trade.size
        if trade.status == TradeStatus.CLOSED.value:
            number_of_trades_closed += 1

        if trade.status == TradeStatus.OPEN.value:
            number_of_trades_open += 1

        if trade.net_gain > 0:
            number_of_positive_trades += 1
        elif trade.net_gain < 0:
            number_of_negative_trades += 1

    if "percentage_positive_trades" in metrics:
        backtest_metrics.percentage_positive_trades = \
            (number_of_positive_trades / len(trades)) * 100.0 \
            if len(trades) > 0 else 0.0

    if "percentage_negative_trades" in metrics:
        backtest_metrics.percentage_negative_trades = \
            (number_of_negative_trades / len(trades)) * 100.0 \
            if len(trades) > 0 else 0.0

    if "number_of_trades" in metrics:
        backtest_metrics.number_of_trades = len(trades)

    if "number_of_trades_closed" in metrics:
        backtest_metrics.number_of_trades_closed = number_of_trades_closed

    if "number_of_trades_open_at_end" in metrics:
        backtest_metrics.number_of_trades_open_at_end = \
            len(trades) - number_of_trades_closed

    number_of_trades = len(trades)

    if 'average_trade_duration' in metrics:
        backtest_metrics.average_trade_duration = \
            total_duration / number_of_trades \
            if number_of_trades > 0 else 0.0

    if 'average_trade_size' in metrics:
        backtest_metrics.average_trade_size = (
            total_trade_size / number_of_trades) \
            if number_of_trades > 0 else 0.0

    if "trades_average_return" in metrics:
        average_return = get_average_return(trades)
        backtest_metrics.trades_average_return = average_return[0]

    if "equity_curve" in metrics:
        backtest_metrics.equity_curve = get_equity_curve(
            backtest_run.portfolio_snapshots
        )

    if "final_value" in metrics:
        backtest_metrics.final_value = get_final_value(
            backtest_run.portfolio_snapshots
        )

    if "cagr" in metrics:
        backtest_metrics.cagr = get_cagr(backtest_run.portfolio_snapshots)

    if "sharpe_ratio" in metrics:
        backtest_metrics.sharpe_ratio = get_sharpe_ratio(
            backtest_run.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        )

    if "rolling_sharpe_ratio" in metrics:
        backtest_metrics.rolling_sharpe_ratio = get_rolling_sharpe_ratio(
            backtest_run.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        )

    if "sortino_ratio" in metrics:
        backtest_metrics.sortino_ratio = get_sortino_ratio(
            backtest_run.portfolio_snapshots, risk_free_rate=risk_free_rate
        )

    if "profit_factor" in metrics:
        backtest_metrics.profit_factor = get_profit_factor(backtest_run.trades)

    if "calmar_ratio" in metrics:
        backtest_metrics.calmar_ratio = \
            get_calmar_ratio(backtest_run.portfolio_snapshots)

    if "annual_volatility" in metrics:
        backtest_metrics.annual_volatility = get_annual_volatility(
            backtest_run.portfolio_snapshots
        )

    if "monthly_returns" in metrics:
        backtest_metrics.monthly_returns = get_monthly_returns(
            backtest_run.portfolio_snapshots
        )

    if "yearly_returns" in metrics:
        backtest_metrics.yearly_returns = get_yearly_returns(
            backtest_run.portfolio_snapshots
        )

    if "drawdown_series" in metrics:
        backtest_metrics.drawdown_series = get_drawdown_series(
            backtest_run.portfolio_snapshots
        )

    if "max_drawdown" in metrics:
        backtest_metrics.max_drawdown = get_max_drawdown(
            backtest_run.portfolio_snapshots
        )

    if "max_drawdown_absolute" in metrics:
        backtest_metrics.max_drawdown_absolute = get_max_drawdown_absolute(
            backtest_run.portfolio_snapshots
        )

    if "max_daily_drawdown" in metrics:
        backtest_metrics.max_daily_drawdown = get_max_daily_drawdown(
            backtest_run.portfolio_snapshots
        )

    if "max_drawdown_duration" in metrics:
        backtest_metrics.max_drawdown_duration = get_max_drawdown_duration(
            backtest_run.portfolio_snapshots
        )

    if "trades_per_year" in metrics:
        backtest_metrics.trades_per_year = get_trades_per_year(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        )

    if "trades_per_day" in metrics:
        backtest_metrics.trades_per_day = get_trades_per_day(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        )

    if "exposure_ratio" in metrics:
        backtest_metrics.exposure_ratio = get_exposure_ratio(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        )

    if "cumulative_exposure" in metrics:
        backtest_metrics.cumulative_exposure = get_cumulative_exposure(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        )

    if "best_trade" in metrics:
        backtest_metrics.best_trade = get_best_trade(backtest_run.trades)

    if "worst_trade" in metrics:
        backtest_metrics.worst_trade = get_worst_trade(backtest_run.trades)

    if 'win_rate' in metrics:
        backtest_metrics.win_rate = get_win_rate(backtest_run.trades)

    if 'win_loss_ratio' in metrics:
        backtest_metrics.win_loss_ratio = \
            get_win_loss_ratio(backtest_run.trades)

    if 'percentage_winning_months' in metrics:
        backtest_metrics.percentage_winning_months = \
            get_percentage_winning_months(
                backtest_run.portfolio_snapshots
            )

    if 'percentage_winning_years' in metrics:
        backtest_metrics.percentage_winning_years = \
            get_percentage_winning_years(backtest_run.portfolio_snapshots)

    if 'percentage_negative_trades' in metrics:
        backtest_metrics.percentage_negative_trades = (
            (number_of_negative_trades / number_of_trades) * 100.0
        ) if number_of_trades > 0 else 0.0

    if 'percentage_positive_trades' in metrics:
        backtest_metrics.percentage_positive_trades = (
            (number_of_positive_trades / number_of_trades) * 100.0
        ) if number_of_trades > 0 else 0.0

    if 'average_monthly_return' in metrics:
        backtest_metrics.average_monthly_return = get_average_monthly_return(
            backtest_run.portfolio_snapshots
        )

    if 'average_monthly_return_winning_months' in metrics:
        backtest_metrics.average_monthly_return_winning_months = \
            get_average_monthly_return_winning_months(
                backtest_run.portfolio_snapshots
            )

    if 'average_monthly_return_losing_months' in metrics:
        backtest_metrics.average_monthly_return_losing_months = \
            get_average_monthly_return_losing_months(
                backtest_run.portfolio_snapshots
            )

    if 'best_month' in metrics:
        backtest_metrics.best_month = get_best_month(
            backtest_run.portfolio_snapshots
        )

    if 'best_year' in metrics:
        backtest_metrics.best_year = get_best_year(
            backtest_run.portfolio_snapshots
        )

    if 'worst_month' in metrics:
        backtest_metrics.worst_month = get_worst_month(
            backtest_run.portfolio_snapshots
        )

    if 'worst_year' in metrics:
        backtest_metrics.worst_year = get_worst_year(
            backtest_run.portfolio_snapshots
        )

    if 'gross_loss' in metrics:
        backtest_metrics.gross_loss = get_gross_loss(backtest_run.trades)

    if 'gross_profit' in metrics:
        backtest_metrics.gross_profit = get_gross_profit(backtest_run.trades)

    if 'growth' in metrics:
        backtest_metrics.growth = get_growth(
            backtest_run.portfolio_snapshots
        )

    if 'growth_percentage' in metrics:
        backtest_metrics.growth_percentage = get_growth_percentage(
            backtest_run.portfolio_snapshots
        )

    if 'cumulative_return_series' in metrics:
        backtest_metrics.cumulative_return_series = \
            get_cumulative_return_series(
                backtest_run.portfolio_snapshots
            )

    if 'cumulative_return' in metrics:
        backtest_metrics.cumulative_return = get_cumulative_return(
            backtest_run.portfolio_snapshots
        )

    return backtest_metrics
