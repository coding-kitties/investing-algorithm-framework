from investing_algorithm_framework.domain import BacktestMetrics, \
    BacktestResult
from .cagr import get_cagr
from .calmar_ratio import get_calmar_ratio
from .drawdown import get_drawdown_series, get_max_drawdown, \
    get_max_daily_drawdown, get_max_drawdown_absolute, \
    get_max_drawdown_duration
from .equity_curve import get_equity_curve
from .exposure import get_exposure, get_trades_per_year, get_trades_per_day, \
    get_average_trade_duration
from .profit_factor import get_profit_factor, get_gross_loss, get_gross_profit
from .returns import get_monthly_returns, get_yearly_returns, \
    get_worst_trade, get_best_trade, get_worst_year, \
    get_best_year, get_best_month, get_worst_month, get_average_gain, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_loss, get_average_monthly_return, \
    get_average_monthly_return_winning_months, \
    get_average_monthly_return_losing_months
from .returns import get_total_return, get_final_value, get_growth, \
    get_growth_percentage
from .sharpe_ratio import get_sharpe_ratio, get_rolling_sharpe_ratio
from .sortino_ratio import get_sortino_ratio
from .volatility import get_annual_volatility
from .win_rate import get_win_rate, get_win_loss_ratio


def create_backtest_metrics(
    backtest_results: BacktestResult, risk_free_rate: float
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

    total_return = get_total_return(backtest_results.portfolio_snapshots)

    return BacktestMetrics(
        backtest_start_date=backtest_results.backtest_start_date,
        backtest_end_date=backtest_results.backtest_end_date,
        equity_curve=get_equity_curve(backtest_results.portfolio_snapshots),
        final_value=get_final_value(backtest_results.portfolio_snapshots),
        total_net_gain=total_return[0],
        total_net_gain_percentage=total_return[1],
        cagr=get_cagr(backtest_results.portfolio_snapshots),
        sharpe_ratio=get_sharpe_ratio(
            backtest_results.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        ),
        rolling_sharpe_ratio=get_rolling_sharpe_ratio(
            backtest_results.portfolio_snapshots,
            risk_free_rate=risk_free_rate
        ),
        sortino_ratio=get_sortino_ratio(
            backtest_results.portfolio_snapshots, risk_free_rate=risk_free_rate
        ),
        profit_factor=get_profit_factor(backtest_results.trades),
        calmar_ratio=get_calmar_ratio(backtest_results.portfolio_snapshots),
        annual_volatility=get_annual_volatility(
            backtest_results.portfolio_snapshots
        ),
        monthly_returns=get_monthly_returns(
            backtest_results.portfolio_snapshots
        ),
        yearly_returns=get_yearly_returns(
            backtest_results.portfolio_snapshots
        ),
        drawdown_series=get_drawdown_series(
            backtest_results.portfolio_snapshots
        ),
        max_drawdown=get_max_drawdown(
            backtest_results.portfolio_snapshots
        ),
        max_drawdown_absolute=get_max_drawdown_absolute(
            backtest_results.portfolio_snapshots
        ),
        max_daily_drawdown=get_max_daily_drawdown(
            backtest_results.portfolio_snapshots
        ),
        max_drawdown_duration=get_max_drawdown_duration(
            backtest_results.portfolio_snapshots
        ),
        trades_per_year=get_trades_per_year(
            backtest_results.trades,
            backtest_results.backtest_start_date,
            backtest_results.backtest_end_date
        ),
        trade_per_day=get_trades_per_day(
            backtest_results.trades,
            backtest_results.backtest_start_date,
            backtest_results.backtest_end_date
        ),
        exposure_factor=get_exposure(
            backtest_results.trades,
            backtest_results.backtest_start_date,
            backtest_results.backtest_end_date
        ),
        trades_average_gain=get_average_gain(
            backtest_results.trades
        ),
        trades_average_loss=get_average_loss(
            backtest_results.trades
        ),
        best_trade=get_best_trade(
            backtest_results.trades
        ),
        worst_trade=get_worst_trade(
            backtest_results.trades
        ),
        average_trade_duration=get_average_trade_duration(
            backtest_results.trades
        ),
        number_of_trades=len(backtest_results.get_trades()),
        win_rate=get_win_rate(backtest_results.trades),
        win_loss_ratio=get_win_loss_ratio(backtest_results.trades),
        percentage_winning_months=get_percentage_winning_months(
            backtest_results.portfolio_snapshots
        ),
        percentage_winning_years=get_percentage_winning_years(
            backtest_results.portfolio_snapshots
        ),
        average_monthly_return=get_average_monthly_return(
            backtest_results.portfolio_snapshots
        ),
        average_monthly_return_winning_months=get_average_monthly_return_winning_months(
            backtest_results.portfolio_snapshots,
        ),
        average_monthly_return_losing_months= get_average_monthly_return_losing_months(
            backtest_results.portfolio_snapshots
        ),
        best_month=get_best_month(
            backtest_results.portfolio_snapshots
        ),
        best_year=get_best_year(
            backtest_results.portfolio_snapshots
        ),
        worst_month=get_worst_month(
            backtest_results.portfolio_snapshots
        ),
        worst_year=get_worst_year(
            backtest_results.portfolio_snapshots
        ),
        gross_loss=get_gross_loss(backtest_results.trades),
        gross_profit=get_gross_profit(backtest_results.trades),
        growth=get_growth(backtest_results.portfolio_snapshots),
        growth_percentage=get_growth_percentage(
            backtest_results.portfolio_snapshots
        )
    )
