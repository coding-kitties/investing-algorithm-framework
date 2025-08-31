from investing_algorithm_framework.domain import BacktestMetrics, \
    TradeStatus, BacktestRun
from .cagr import get_cagr
from .calmar_ratio import get_calmar_ratio
from .drawdown import get_drawdown_series, get_max_drawdown, \
    get_max_daily_drawdown, get_max_drawdown_absolute, \
    get_max_drawdown_duration
from .equity_curve import get_equity_curve
from .exposure import get_exposure_ratio, get_cumulative_exposure, \
    get_trades_per_year, get_trades_per_day, \
    get_average_trade_duration
from .profit_factor import get_profit_factor, get_gross_loss, get_gross_profit
from .returns import get_monthly_returns, get_yearly_returns, \
    get_worst_trade, get_best_trade, get_worst_year, \
    get_best_year, get_best_month, get_worst_month, get_average_gain, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_loss, get_average_monthly_return, \
    get_average_monthly_return_winning_months, get_average_return, \
    get_average_monthly_return_losing_months
from .returns import get_total_return, get_final_value, get_growth, \
    get_growth_percentage
from .sharpe_ratio import get_sharpe_ratio, get_rolling_sharpe_ratio
from .sortino_ratio import get_sortino_ratio
from .volatility import get_annual_volatility
from .win_rate import get_win_rate, get_win_loss_ratio


def create_backtest_metrics(
    backtest_run: BacktestRun, risk_free_rate: float
) -> BacktestMetrics:
    """
    Create a BacktestMetrics instance and optionally save it to a file.

    Args:
        backtest_results (BacktestResult): The results of the backtest
            containing portfolio snapshots and other metrics.
        risk_free_rate (float): The risk-free rate to use in calculations,

    Returns:
        BacktestMetrics: The created BacktestMetrics instance.
    """

    total_return = get_total_return(backtest_run.portfolio_snapshots)
    trades_average_gain = get_average_gain(
        backtest_run.trades
    )
    trades_average_loss = get_average_loss(
        backtest_run.trades
    )

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

    percentage_positive_trades = \
        (number_of_positive_trades / len(trades)) * 100.0 \
        if len(trades) > 0 else 0.0
    percentage_negative_trades = \
        (number_of_negative_trades / len(trades)) * 100.0 \
        if len(trades) > 0 else 0.0
    number_of_trades_closed = number_of_trades_closed
    number_of_trades_open = number_of_trades_open
    number_of_trades = len(trades)
    average_trade_size = \
        total_trade_size / number_of_trades \
        if number_of_trades > 0 else 0.0
    average_return = get_average_return(trades)

    return BacktestMetrics(
        backtest_start_date=backtest_run.backtest_start_date,
        backtest_end_date=backtest_run.backtest_end_date,
        equity_curve=get_equity_curve(backtest_run.portfolio_snapshots),
        final_value=get_final_value(backtest_run.portfolio_snapshots),
        total_net_gain=total_return[0],
        total_net_gain_percentage=total_return[1],
        cagr=get_cagr(backtest_run.portfolio_snapshots),
        sharpe_ratio=get_sharpe_ratio(
            backtest_run.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        ),
        rolling_sharpe_ratio=get_rolling_sharpe_ratio(
            backtest_run.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        ),
        sortino_ratio=get_sortino_ratio(
            backtest_run.portfolio_snapshots, risk_free_rate=risk_free_rate
        ),
        profit_factor=get_profit_factor(backtest_run.trades),
        calmar_ratio=get_calmar_ratio(backtest_run.portfolio_snapshots),
        annual_volatility=get_annual_volatility(
            backtest_run.portfolio_snapshots
        ),
        monthly_returns=get_monthly_returns(
            backtest_run.portfolio_snapshots
        ),
        yearly_returns=get_yearly_returns(
            backtest_run.portfolio_snapshots
        ),
        drawdown_series=get_drawdown_series(
            backtest_run.portfolio_snapshots
        ),
        max_drawdown=get_max_drawdown(
            backtest_run.portfolio_snapshots
        ),
        max_drawdown_absolute=get_max_drawdown_absolute(
            backtest_run.portfolio_snapshots
        ),
        max_daily_drawdown=get_max_daily_drawdown(
            backtest_run.portfolio_snapshots
        ),
        max_drawdown_duration=get_max_drawdown_duration(
            backtest_run.portfolio_snapshots
        ),
        trades_per_year=get_trades_per_year(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        ),
        trade_per_day=get_trades_per_day(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        ),
        exposure_ratio=get_exposure_ratio(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        ),
        cumulative_exposure=get_cumulative_exposure(
            backtest_run.trades,
            backtest_run.backtest_start_date,
            backtest_run.backtest_end_date
        ),
        trades_average_gain=trades_average_gain[0],
        trades_average_gain_percentage=trades_average_gain[1],
        trades_average_loss=trades_average_loss[0],
        trades_average_loss_percentage=trades_average_loss[1],
        trades_average_return=average_return[0],
        trades_average_return_percentage=average_return[1],
        best_trade=get_best_trade(
            backtest_run.trades
        ),
        worst_trade=get_worst_trade(
            backtest_run.trades
        ),
        average_trade_duration=get_average_trade_duration(
            backtest_run.trades
        ),
        average_trade_size=average_trade_size,
        number_of_trades=len(backtest_run.get_trades()),
        win_rate=get_win_rate(backtest_run.trades),
        win_loss_ratio=get_win_loss_ratio(backtest_run.trades),
        percentage_winning_months=get_percentage_winning_months(
            backtest_run.portfolio_snapshots
        ),
        percentage_winning_years=get_percentage_winning_years(
            backtest_run.portfolio_snapshots
        ),
        percentage_negative_trades=percentage_negative_trades,
        percentage_positive_trades=percentage_positive_trades,
        average_monthly_return=get_average_monthly_return(
            backtest_run.portfolio_snapshots
        ),
        average_monthly_return_winning_months=get_average_monthly_return_winning_months(
            backtest_run.portfolio_snapshots,
        ),
        average_monthly_return_losing_months= get_average_monthly_return_losing_months(
            backtest_run.portfolio_snapshots
        ),
        best_month=get_best_month(
            backtest_run.portfolio_snapshots
        ),
        best_year=get_best_year(
            backtest_run.portfolio_snapshots
        ),
        worst_month=get_worst_month(
            backtest_run.portfolio_snapshots
        ),
        worst_year=get_worst_year(
            backtest_run.portfolio_snapshots
        ),
        gross_loss=get_gross_loss(backtest_run.trades),
        gross_profit=get_gross_profit(backtest_run.trades),
        growth=get_growth(backtest_run.portfolio_snapshots),
        growth_percentage=get_growth_percentage(
            backtest_run.portfolio_snapshots
        )
    )
