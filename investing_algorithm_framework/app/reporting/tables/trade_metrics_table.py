import pandas as pd

from investing_algorithm_framework.domain import DEFAULT_DATETIME_FORMAT
from .utils import safe_format, safe_format_date, safe_format_percentage


def highlight_win_rate(row):
    """
    | **Winning Percentage** | **Interpretation**                                                   |
    |-------------------------|----------------------------------------------------------------------|
    | **< 40%**               | 🟥 Poor — Strategy may not be viable                                 |
    | **40% to 50%**          | 🟧 Weak — Needs improvement, often breakeven or slightly negative     |
    | **50% to 60%**          | 🟨 Average — Acceptable for many strategies, especially with high PF  |
    | **60% to 70%**          | 🟩 Good — Solid performance, often with good risk/reward              |
    | **> 70%**               | 🟩 Excellent — High win rate, typically indicates a strong edge       |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'].strip('%'))
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Win Rate' and value is not None:
        if value < 40:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
        elif 40 <= value < 50:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif 50 <= value < 60:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 60 <= value < 70:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif value >= 70:
            styles['Value'] = 'color: #228B22; font-weight: bold;'  # dark green
    return styles


def highlight_win_loss_ratio(row):
    """
    | **Win/Loss Ratio** | **Interpretation**                                                   |
    |---------------------|----------------------------------------------------------------------|
    | **< 0.5**           | 🟥 Poor — Strategy may not be viable                                 |
    | **0.5 to 1.0**      | 🟧 Weak — Needs improvement, often breakeven or slightly negative     |
    | **1.0 to 1.5**      | 🟨 Average — Acceptable for many strategies, especially with high PF  |
    | **1.5 to 2.0**      | 🟩 Good — Solid performance, often with good risk/reward              |
    | **> 2.0**           | 🟩 Excellent — High win/loss ratio, typically indicates a strong edge |
    """
    metric = row['Metric']
    try:
        value = float(row['Value'])
    except Exception:
        value = None
    styles = pd.Series('', index=row.index)
    if metric == 'Win/Loss Ratio' and value is not None:
        if value < 0.5:
            styles['Value'] = 'color: #B22222; font-weight: bold;'  # red
        elif 0.5 <= value < 1.0:
            styles['Value'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif 1.0 <= value < 1.5:
            styles['Value'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 1.5 <= value < 2.0:
            styles['Value'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif value >= 2.0:
            styles['Value'] = 'color: #228B22; font-weight: bold;'  # dark green
    return styles


def create_html_trade_metrics_table(results, report):
    copy_results = results.to_dict().copy()
    string_format = "{:.2f}"
    copy_results['Trades per Year'] = safe_format(copy_results['trades_per_year'], string_format)
    copy_results['Trades per Day'] =  safe_format(copy_results['trade_per_day'], string_format)
    copy_results['Exposure Ratio'] = safe_format(copy_results['exposure_ratio'],string_format)
    copy_results["Cumulative Exposure"] = safe_format(copy_results['cumulative_exposure'],string_format)
    best_trade = copy_results['best_trade']

    if best_trade is None:
        copy_results["Best Trade"] = "N/A"
        copy_results['Best Trade Date'] = "N/A"
    else:
        copy_results['Best Trade'] = f"{best_trade['net_gain']:.2f} {report.trading_symbol}"
        copy_results['Best Trade Date'] = safe_format_date(best_trade["opened_at"], format_str=DEFAULT_DATETIME_FORMAT)
    worst_trade = copy_results['worst_trade']

    if worst_trade is None:
        copy_results["Worst Trade"] = "N/A"
        copy_results['Worst Trade Date'] = "N/A"
    else:
        copy_results['Worst Trade'] = f"{worst_trade['net_gain']:.2f} {report.trading_symbol}"
        copy_results['Worst Trade Date'] = safe_format_date(worst_trade['opened_at'], format_str=DEFAULT_DATETIME_FORMAT)

    copy_results['Trades Average Gain'] = f"{safe_format(copy_results['average_trade_gain'], string_format)} {report.trading_symbol} {copy_results['trades_average_gain_percentage']:.2f}%"
    copy_results['Trades Average Loss'] = f"{safe_format(copy_results['average_trade_loss'], string_format)} {report.trading_symbol} {copy_results['trades_average_loss_percentage']:.2f}%"
    copy_results['Average Trade Duration'] = f"{copy_results['average_trade_duration']:.2f} hours"
    copy_results['Number of Trades'] = f"{copy_results['number_of_trades']}"
    copy_results['Win Rate'] = f"{copy_results['win_rate']:.2f}%"
    copy_results['Win/Loss Ratio'] = f"{copy_results['win_loss_ratio']:.2f}"

    stats = {
        "Metric": [
            "Trades per Year",
            "Trade per Day",
            "Exposure Ratio",
            "Cumulative Exposure",
            "Trades Average Gain",
            "Trades Average Loss",
            "Best Trade",
            "Best Trade Date",
            "Worst Trade",
            "Worst Trade Date",
            "Average Trade Duration",
            "Number of Trades",
            "Win Rate",
            "Win/Loss Ratio"
        ],
        "Value": [
            copy_results['Trades per Year'],
            copy_results['Trades per Day'],
            copy_results['Exposure Ratio'],
            copy_results['Cumulative Exposure'],
            copy_results['Trades Average Gain'],
            copy_results['Trades Average Loss'],
            copy_results['Best Trade'],
            copy_results['Best Trade Date'],
            copy_results['Worst Trade'],
            copy_results['Worst Trade Date'],
            copy_results['Average Trade Duration'],
            copy_results['Number of Trades'],
            copy_results['Win Rate'],
            copy_results['Win/Loss Ratio']
        ]
    }

    df_stats = pd.DataFrame(stats)

    table_html = (
        df_stats.style
        .apply(highlight_win_rate, axis=1)
        .apply(highlight_win_loss_ratio, axis=1)
        .set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#f2f2f2'), ('font-weight', 'bold')]},
            {'selector': 'td', 'props': [('font-size', '14px')]},
            {'selector': 'tr:nth-child(even)', 'props': [('background-color', '#fafafa')]}
        ])
        .hide(axis='index')
        .to_html()
    )
    return table_html