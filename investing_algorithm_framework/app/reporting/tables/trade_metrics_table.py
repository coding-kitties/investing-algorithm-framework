import pandas as pd

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
    copy_results = results.copy()
    copy_results['Trades per Year'] = safe_format(copy_results['Trades per Year'], "{:.2f}")
    copy_results['Trades per Day'] =  safe_format(copy_results['Trade per day'], "{:.2f}")
    copy_results['Exposure Factor'] =  safe_format(copy_results['Exposure'], "{:.2f}")
    best_trade = copy_results['Best Trade']

    if best_trade is None:
        copy_results["Best Trade"] = "N/A"
        copy_results['Best Trade Date'] = "N/A"
    else:
        copy_results['Best Trade'] = f"{copy_results['Best Trade'].net_gain:.2f} {report.trading_symbol} ({copy_results['Best Trade'].net_gain_percentage:.2f})%"
        copy_results['Best Trade Date'] = copy_results['Best Trade Date'].strftime('%Y-%m-%d')

    worst_trade = copy_results['Worst Trade']

    if worst_trade is None:
        copy_results["Worst Trade"] = "N/A"
        copy_results['Worst Trade Date'] = "N/A"
    else:
        copy_results['Worst Trade'] = f"{copy_results['Worst Trade'].net_gain:.2f} {report.trading_symbol} ({copy_results['Worst Trade'].net_gain_percentage:.2f})%"
        copy_results['Worst Trade Date'] = copy_results['Worst Trade Date'].strftime('%Y-%m-%d')

    copy_results['Trades Average Gain'] = f"{copy_results['Trades average gain'][0]:.2f} {report.trading_symbol} {copy_results['Trades average gain'][1]:.2f}%"
    copy_results['Trades Average Loss'] = f"{copy_results['Trades average loss'][1]:.2f} {report.trading_symbol} {copy_results['Trades average loss'][1]:.2f}%"
    copy_results['Average Trade Duration'] = f"{copy_results['Average Trade Duration']:.2f} hours"
    copy_results['Number of Trades'] = f"{copy_results['Number of Trades']}"
    copy_results['Win Rate'] = f"{copy_results['Win Rate']:.2f}%"
    copy_results['Win/Loss Ratio'] = f"{copy_results['Win/Loss Ratio']:.2f}"

    stats = {
        "Metric": [
            "Trades per Year",
            "Trade per Day",
            "Exposure Factor",
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
            copy_results['Exposure Factor'],
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