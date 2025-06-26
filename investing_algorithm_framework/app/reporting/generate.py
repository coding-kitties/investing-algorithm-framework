import os
from jinja2 import Environment, FileSystemLoader

from .tables import create_html_time_metrics_table, \
    create_html_trade_metrics_table, create_html_key_metrics_table, \
    create_html_trades_table
from .charts import get_equity_curve_with_drawdown_chart, \
    get_rolling_sharp_ratio_chart, get_monthly_returns_heatmap_chart, \
    get_yearly_returns_bar_chart
from .metrics import get_equity_curve, get_total_return, get_cagr, \
    get_sharpe_ratio, get_rolling_sharpe_ratio, get_sortino_ratio, \
    get_profit_factor, get_calmar_ratio, get_annual_volatility, \
    get_monthly_returns, get_yearly_returns, get_drawdown_series, \
    get_max_drawdown, get_max_drawdown_absolute, get_max_daily_drawdown, \
    get_max_drawdown_duration, get_trade_frequency, \
    get_exposure, get_win_rate, get_average_gain, get_average_loss, \
    get_best_trade, get_best_trade_date, get_worst_trade, \
    get_worst_trade_date, get_average_trade_duration, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_monthly_return, \
    get_average_monthly_return_losing_months, get_win_loss_ratio, \
    get_average_monthly_return_winning_months, get_best_month, \
    get_best_year, get_worst_month, get_worst_year, get_trades_per_year


def add_metrics(report, risk_free_rate=None) -> "BacktestReport":
    """
    Add metrics to the report.results.

    Args:
        report (BacktestReport): The backtest report.results to
            which the metrics will be added.
        risk_free_rate (float, optional): The risk-free rate to be used in
            the report.results calculations. Defaults to None. If none, the
            risk-free rate will be retrieved from the US Treasury (10-year
            yield) using the `get_risk_free_rate` function.
    """
    results = {
        "backtest_start_date": report.results.backtest_start_date,
        "backtest_end_date": report.results.backtest_end_date,
        "Equity Curve": get_equity_curve(report.results.portfolio_snapshots),
        "Total Return": get_total_return(report.results.portfolio_snapshots),
        "CAGR": get_cagr(report.results.portfolio_snapshots),
        "Sharpe Ratio": get_sharpe_ratio(report.results.portfolio_snapshots),
        "Rolling Sharpe Ratio": get_rolling_sharpe_ratio(
            report.results.portfolio_snapshots, risk_free_rate=risk_free_rate
        ),
        "Sortino Ratio": get_sortino_ratio(
            report.results.portfolio_snapshots, risk_free_rate=risk_free_rate
        ),
        "Profit Factor": get_profit_factor(report.results.get_trades()),
        "Calmar Ratio": get_calmar_ratio(report.results.portfolio_snapshots),
        "Annual Volatility": get_annual_volatility(
            report.results.portfolio_snapshots
        ),
        "Monthly Returns": get_monthly_returns(
            report.results.portfolio_snapshots
        ),
        "Yearly Returns": get_yearly_returns(
            report.results.portfolio_snapshots
        ),
        "Drawdown series": get_drawdown_series(
            report.results.portfolio_snapshots
        ),
        "Max Drawdown": get_max_drawdown(
            report.results.portfolio_snapshots
        ),
        "Max Drawdown Absolute": get_max_drawdown_absolute(
            report.results.portfolio_snapshots),
        "Max Daily Drawdown": get_max_daily_drawdown(
            report.results.portfolio_snapshots
        ),
        "Max Drawdown Duration": get_max_drawdown_duration(
            report.results.portfolio_snapshots
        ),
        "Trades per Year": get_trades_per_year(
            report.results.get_trades(),
            report.results.backtest_start_date,
            report.results.backtest_end_date
        ),
        "Trade per day": get_trade_frequency(
            report.results.get_trades(),
            report.results.backtest_start_date,
            report.results.backtest_end_date
        ),
        "Exposure": get_exposure(
            report.results.get_trades(),
            report.results.backtest_start_date,
            report.results.backtest_end_date
        ),
        "Trades winning percentage": get_win_rate(report.results.get_trades()),
        "Trades average gain": get_average_gain(report.results.get_trades()),
        "Trades average loss": get_average_loss(report.results.get_trades()),
        "Best Trade": get_best_trade(report.results.get_trades()),
        "Best Trade Date": get_best_trade_date(report.results.get_trades()),
        "Worst Trade": get_worst_trade(report.results.get_trades()),
        "Worst Trade Date": get_worst_trade_date(report.results.get_trades()),
        "Average Trade Duration": get_average_trade_duration(
            report.results.get_trades()),
        "Number of Trades": len(report.results.get_trades()),
        "Win Rate": get_win_rate(report.results.get_trades()),
        "Win/Loss Ratio": get_win_loss_ratio(report.results.get_trades()),
        "Percentage Winning Months": get_percentage_winning_months(
            report.results.portfolio_snapshots),
        "Percentage Winning Years": get_percentage_winning_years(
            report.results.portfolio_snapshots),
        "Average Monthly Return": get_average_monthly_return(
            report.results.portfolio_snapshots),
        "Average Monthly Return (Losing Months)":
            get_average_monthly_return_losing_months(
                report.results.portfolio_snapshots
            ),
        "Average Monthly Return (Winning Months)":
            get_average_monthly_return_winning_months(
                report.results.portfolio_snapshots
            ),
        "Best Month": get_best_month(report.results.portfolio_snapshots),
        "Best Year": get_best_year(report.results.portfolio_snapshots),
        "Worst Month": get_worst_month(report.results.portfolio_snapshots),
        "Worst Year": get_worst_year(report.results.portfolio_snapshots),
    }
    report.metrics = results
    return report

def add_html_report(report) -> "BacktestReport":
    """
    Add HTML content to the report.results.

    Args:
        report.results (Backtestreport.results): The backtest report.results to which the HTML
            content will be added.

    Returns:
        Backtestreport.results: The updated report.results with HTML content.
    """
    metrics = report.metrics
    # Create plots
    equity_with_drawdown_fig = get_equity_curve_with_drawdown_chart(
        metrics["Equity Curve"], metrics["Drawdown series"]
    )
    equity_with_drawdown_plot_html = equity_with_drawdown_fig.to_html(
        full_html=False, include_plotlyjs='cdn',
        config={'responsive': True}, default_width="90%"
    )
    rolling_sharpe_ratio_fig = get_rolling_sharp_ratio_chart(
        metrics["Rolling Sharpe Ratio"]
    )
    rolling_sharpe_ratio_plot_html = rolling_sharpe_ratio_fig.to_html(
        full_html=False, include_plotlyjs='cdn',
        config={'responsive': True}, default_width="90%"
    )
    monthly_returns_heatmap_fig = get_monthly_returns_heatmap_chart(
        metrics["Monthly Returns"]
    )
    monthly_returns_heatmap_html = monthly_returns_heatmap_fig.to_html(
        full_html=False, include_plotlyjs='cdn',
        config={'responsive': True}
    )
    yearly_returns_histogram_fig = get_yearly_returns_bar_chart(
        metrics["Yearly Returns"]
    )
    yearly_returns_histogram_html = yearly_returns_histogram_fig.to_html(
        full_html=False, include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # Create HTML tables
    key_metrics_table_html = create_html_key_metrics_table(
        metrics, report.results
    )
    trades_metrics_table_html = create_html_trade_metrics_table(
        metrics, report.results
    )
    time_metrics_table_html = create_html_time_metrics_table(
        metrics, report.results
    )
    trades_table_html = create_html_trades_table(
        report.results
    )

    # Jinja2 environment setup
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('report_template.html.j2')

    # Render template with variables
    html_rendered = template.render(
        report=report,
        equity_with_drawdown_plot_html=equity_with_drawdown_plot_html,
        rolling_sharpe_ratio_plot_html=rolling_sharpe_ratio_plot_html,
        monthly_returns_heatmap_html=monthly_returns_heatmap_html,
        yearly_returns_histogram_html=yearly_returns_histogram_html,
        key_metrics_table_html=key_metrics_table_html,
        trades_metrics_table_html=trades_metrics_table_html,
        time_metrics_table_html=time_metrics_table_html,
        trades_table_html=trades_table_html,
    )
    report.html_report = html_rendered
    return report
