import pandas as pd


def highlight_net_gain(row):
    """
    Apply conditional formatting to the 'Net Gain' column based on numeric value.
    """
    try:
        # Extract numeric value before the first space (assumes format like "123.45 USDT (10.23%)")
        value_str = row['Net Gain'].split()[2]
        value_str = value_str.split('(')[1]
        value_str = value_str.replace(')', '').strip()
        if '%' in value_str:
            value_str = value_str.replace('%', '')
        value = float(value_str)

    except Exception:
        value = None

    styles = pd.Series('', index=row.index)

    if value is not None:
        if value < -5:
            styles['Net Gain'] = 'color: #B22222; font-weight: bold;'  # red
        elif -5 <= value < -2:
            styles['Net Gain'] = 'color: #FFA500; font-weight: bold;'  # orange
        elif -2 <= value < 0:
            styles['Net Gain'] = 'color: #FFD700; font-weight: bold;'  # gold
        elif 0 <= value < 5:
            styles['Net Gain'] = 'color: #32CD32; font-weight: bold;'  # lime green
        elif value >= 5:
            styles['Net Gain'] = 'color: #228B22; font-weight: bold;'  # dark green

    return styles

def get_exit(trade):
    """
    Returns the exit price of a trade if it is closed, otherwise returns "open".
    This is used to display the exit price in the trades table.

    A trade can have multiple exits and close prices.
    """

    if trade.closed_at:
        return f"{trade.closed_at.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        return "open"


def create_html_trades_table(report):
    trades = report.get_trades()

    # Create a DataFrame from the trades, with the attributes id, net_gain, net_gain_percentage, entry_time, exit_time, duration, and symbol
    selection = {
        'Trade': [f"{trade.id} {trade.target_symbol}/{trade.trading_symbol}" for trade in trades],
        'Net Gain': [f"{trade.change:.2f} {report.trading_symbol} ({trade.percentage_change:.2f}%)" for trade in trades],
        'Entry (Price, Date)': [f"{trade.open_price} {trade.opened_at.strftime('%Y-%m-%d %H:%M:%S')}" for trade in trades],
        'Exit (Price, Date)': [get_exit(trade) for trade in trades],
        'Duration': [f"{trade.duration:.2f} hours" for trade in trades],
    }
    trades_df = pd.DataFrame(selection)

    table_html = (
        trades_df.style
        .apply(highlight_net_gain, axis=1)
        # .apply(highlight_win_loss_ratio, axis=1)
        .set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#f2f2f2'), ('font-weight', 'bold')]},
            {'selector': 'td', 'props': [('font-size', '14px')]},
            {'selector': 'tr:nth-child(even)', 'props': [('background-color', '#fafafa')]}
        ])
        .hide(axis='index')
        .to_html(classes='display', index=False, table_id='tradesTable')
    )
    return table_html