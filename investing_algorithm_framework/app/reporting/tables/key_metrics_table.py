import pandas as pd

from .utils import safe_format, safe_format_percentage


def highlight_sharpe_and_sortino(row):
    """
    | -------------- | ------------------------------------------- |
    | **< 0**        | Bad: Underperforms risk-free asset          |
    | **0.0 – 1.0**  | Suboptimal: Returns do not justify risk     |
    | **1.0 – 1.99** | Acceptable: Reasonable risk-adjusted return |
    | **2.0 – 2.99** | Good: Strong risk-adjusted performance      |
    | **3.0+**       | Excellent: Exceptional risk-adjusted return |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'])
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric in ['Sharpe Ratio', 'Sortino Ratio'] and value is not None:

        if value < 0:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
        elif 0 <= value < 1:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif 1 <= value < 2:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 2 <= value < 3:
            styles['Value'] = 'color: #32CD32; font-weight: bold;' # lime green
        elif value >= 3:
            styles['Value'] = 'color: #228B22; font-weight: bold;' # dark green
    return styles


def highlight_profit_factor(row):
    """
    | **< 1.0**         | **Losing strategy** — losses outweigh profits                                             |
    | **1.0 – 1.3**     | Weak or barely breakeven — needs improvement or may not be sustainable                    |
    | **1.3 – 1.6**     | Average — possibly profitable but sensitive to market regime changes                      |
    | **1.6 – 2.0**     | Good — generally indicates a solid, sustainable edge                                      |
    | **2.0 – 3.0**     | Very good — strong edge with lower drawdown risk                                          |
    | **> 3.0**         | Excellent — rare in real markets; often associated with low-frequency or niche strategies |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'])
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Profit Factor' and value is not None:
        if value < 1.0:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
        elif 1.0 <= value < 1.3:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif 1.3 <= value < 1.6:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 1.6 <= value < 2.0:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif 2.0 <= value < 3.0:
            styles['Value'] = 'color: #228B22; font-weight: bold;'  # dark green
        elif value >= 3.0:
            styles['Value'] = 'color: #006400; font-weight: bold;'  # dark green
    return styles

def highlight_calmar_ratio(row):
    """
    | **> 3.0**        | **Excellent** – strong return vs. drawdown                  |
    | **2.0 – 3.0**    | **Very Good** – solid risk-adjusted performance             |
    | **1.0 – 2.0**    | **Acceptable** – decent, especially for volatile strategies |
    | **< 1.0**        | **Poor** – high drawdowns relative to return                |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'])
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Calmar Ratio' and value is not None:
        if value > 3.0:
            styles['Value'] = 'color: #006400; font-weight: bold;'  # dark green
        elif 2.0 <= value <= 3.0:
            styles['Value'] = 'color: #228B22; font-weight: bold;'  # green
        elif 1.0 <= value < 2.0:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif value < 1.0:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
    return styles


def highlight_annual_volatility(row):
    """
    | **Annual Volatility** | **Risk Level** | **Typical for...**                                                     | **Comments**                                                                    |
    | --------------------- | -------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
    | **< 5%**              | Very Low Risk  | Cash equivalents, short-term bonds                                     | Low return expectations; often used for capital preservation                    |
    | **5% – 10%**          | Low Risk       | Diversified bond portfolios, conservative allocation strategies        | Suitable for risk-averse investors                                              |
    | **10% – 15%**         | Moderate Risk  | Balanced portfolios, large-cap equity indexes (e.g., S\&P 500 ≈ \~15%) | Standard for traditional diversified portfolios                                 |
    | **15% – 25%**         | High Risk      | Growth stocks, hedge funds, active equity strategies                   | Higher return potential, but more drawdowns                                     |
    | **> 25%**             | Very High Risk | Crypto, leveraged ETFs, speculative strategies                         | High potential returns, but prone to large losses; often not suitable long-term |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'].strip('%')) / 100  # Convert percentage string to float
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Annual Volatility' and value is not None:
        if value < 0.05:
            styles['Value'] = 'color: #006400; font-weight: bold;'  # dark green
        elif 0.05 <= value < 0.10:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif 0.10 <= value < 0.15:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 0.15 <= value < 0.25:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif value >= 0.25:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
    return styles


def highlight_max_drawdown(row):
    """
    | **Max Drawdown (%)** | **Interpretation**                                                   |
    |-----------------------|----------------------------------------------------------------------|
    | **0% to -5%**         | 🟢 Excellent — Very low risk, typical for conservative strategies     |
    | **-5% to -10%**       | ✅ Good — Moderate volatility, acceptable for balanced portfolios     |
    | **-10% to -20%**      | ⚠️ Elevated Risk — Common in growth or actively managed strategies    |
    | **-20% to -40%**      | 🔻 High Risk — Significant drawdown, typical of aggressive strategies |
    | **> -40%**            | 🚨 Very High Risk — Risk of capital loss or strategy failure          |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'].strip('%'))
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Max Drawdown' and value is not None:
        if value < 5:
            styles['Value'] = 'color: #006400; font-weight: bold;'  # dark green
        elif 10 >= value > 5:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif 20 >= value > 10:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 40 >= value > 20:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif value >= 40:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
    return styles


def create_html_key_metrics_table(results, report):
    copy_results = results.to_dict().copy()
    format_str = "{:.2f}"

    # Format some values to percentages and floats
    copy_results['Total Return'] = (
        f"{safe_format(copy_results['total_net_gain'], format_str)} "
        f"({safe_format_percentage(copy_results['total_net_gain_percentage'], format_str)}%)"
    )
    copy_results['CAGR'] = f"{safe_format_percentage(copy_results['cagr'],format_str)}%"
    copy_results['Sharpe Ratio'] = safe_format(copy_results['sharpe_ratio'], format_str)
    copy_results['Sortino Ratio'] = safe_format(copy_results['sortino_ratio'], format_str)
    copy_results['Profit Factor'] = safe_format(copy_results['profit_factor'], format_str)
    copy_results['Calmar Ratio'] = safe_format(copy_results['calmar_ratio'], format_str)
    copy_results['Annual Volatility'] = f"{safe_format_percentage(copy_results['annual_volatility'], format_str)}%"
    copy_results['Max Drawdown'] = f"{safe_format_percentage(copy_results['max_drawdown'], format_str)}%"
    copy_results['Max Drawdown Absolute'] = f"{safe_format(copy_results['max_drawdown_absolute'], format_str)} {report.trading_symbol}"
    copy_results['Max Daily Drawdown'] = f"{safe_format_percentage(copy_results['max_daily_drawdown'], format_str)}%"
    copy_results['Max Drawdown Duration'] = f"{copy_results['max_drawdown_duration']} hours - {copy_results['max_drawdown_duration'] // 24} days"

    stats = {
        "Metric": [
            "Total Return",
            "CAGR",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Profit Factor",
            "Calmar Ratio",
            "Annual Volatility",
            "Max Drawdown",
            "Max Drawdown Absolute",
            "Max Daily Drawdown",
            "Max Drawdown Duration"
        ],
        "Value": [
            copy_results['Total Return'],
            copy_results['CAGR'],
            copy_results['Sharpe Ratio'],
            copy_results['Sortino Ratio'],
            copy_results['Profit Factor'],
            copy_results['Calmar Ratio'],
            copy_results['Annual Volatility'],
            copy_results['Max Drawdown'],
            copy_results['Max Drawdown Absolute'],
            copy_results['Max Daily Drawdown'],
            copy_results['Max Drawdown Duration']
        ]
    }

    df_stats = pd.DataFrame(stats)

    table_html = (
        df_stats.style
        .apply(highlight_sharpe_and_sortino, axis=1)
        .apply(highlight_profit_factor, axis=1)
        .apply(highlight_calmar_ratio, axis=1)
        .apply(highlight_annual_volatility, axis=1)
        .apply(highlight_max_drawdown, axis=1)
        .set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#f2f2f2'), ('font-weight', 'bold')]},
            {'selector': 'td', 'props': [('font-size', '14px')]},
            {'selector': 'tr:nth-child(even)', 'props': [('background-color', '#fafafa')]}
        ])
        .hide(axis='index')
        .to_html()
    )
    return table_html
