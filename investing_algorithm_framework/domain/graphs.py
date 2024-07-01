import pandas as pd
import plotly.graph_objs as go


def create_rsi_graph(data: pd.DataFrame):
    """
    Create a graph for the RSI metric.
    :param data: DataFrame with a 'RSI' column and a Datetime index
    :return: Plotly graph object
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")


    # Check if the 'RSI' column exists
    if 'RSI' not in data.columns:
        raise ValueError("The data should have a 'RSI' column")

    return go.Scatter(
        x=data.index,
        y=data['RSI'],
        mode='lines',
        line=dict(color="green", width=1),
        name="RSI"
    )


def create_prices_graph(
    data: pd.DataFrame,
    data_key="Close",
    graph_name="Price",
    color="blue",
    line_width=1
):
    """
    Create a graph for the close prices. By default, the key is set to 'Close'.

    Args:
        data (pd.DataFrame): The data to plot
        data_key (str): The key to use for the prices
        graph_name (str): The name of the graph
        color (str): The color of the graph
        line_width (int): The width of the line

    Returns:
        go.Scatter: The Plotly graph object
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the 'Close' column exists
    if data_key not in data.columns:
        raise ValueError("The data should have a 'Close' column")

    return go.Scatter(
        x=data.index,
        y=data[data_key],
        mode='lines',
        line=dict(color=color, width=line_width),
        name=graph_name
    )

def create_adx_graph(data: pd.DataFrame):
    """
    Create a graph for the ADX metric.
    :param data: DataFrame with a 'ADX' column and a Datetime index
    :return: Plotly graph object
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the 'ADX' column exists
    if 'ADX' not in data.columns:
        raise ValueError("The data should have a 'ADX' column")

    return go.Scatter(
        x=data.index,
        y=data['ADX'],
        mode='lines',
        line=dict(color="green", width=1),
        name="ADX"
    )

def create_di_plus_graph(data: pd.DataFrame):
    """
    Create a graph for the DI+ metric.
    :param data: DataFrame with a '+DI' column and a Datetime index
    :return: Plotly graph object
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the '+DI' column exists
    if '+DI' not in data.columns:
        raise ValueError("The data should have a '+DI' column")

    return go.Scatter(
        x=data.index,
        y=data['+DI'],
        mode='lines',
        line=dict(color="orange", width=1),
        name="+DI"
    )

def create_di_minus_graph(data: pd.DataFrame):
    """
    Create a graph for the DI- metric.
    :param data: DataFrame with a '-DI' column and a Datetime index
    :return: Plotly graph object
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the '-DI' column exists
    if '-DI' not in data.columns:
        raise ValueError("The data should have a '-DI' column")

    return go.Scatter(
        x=data.index,
        y=data['-DI'],
        mode='lines',
        line=dict(color="purple", width=1),
        name="-DI"
    )

def create_di_plus_di_minus_crossover_graph(data: pd.DataFrame):
    """
    Create a graph for the DI- and DI+ crossover.
    """

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the '-DI' and '+DI' columns exist
    if '-DI' not in data.columns or '+DI' not in data.columns:
        raise ValueError("The data should have a '-DI' and '+DI' column")

    # Get all crossover indexes
    crossover_index = data[(data['+DI'] < data['-DI']) & (data['+DI'].shift(1) > data['-DI'].shift(1))].index

    # Use .loc to get the corresponding 'Close' values
    crossover_close_values = data.loc[crossover_index, '+DI']

    return go.Scatter(
        x=crossover_index,
        y=crossover_close_values,
        mode='markers',
        marker=dict(symbol='circle', size=10, color='blue'),
        name='DI- DI+ Crossover'
    )


def create_ema_graph(data: pd.DataFrame, key, color="blue"):
    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the key columns exist
    if key not in data.columns:
        raise ValueError(f"The data should have a {key} column")


    return go.Scatter(
        x=data.index,
        y=data[key],
        mode='lines',
        line=dict(color=color, width=1),
        name=key
    )

def create_crossover_graph(data: pd.DataFrame, key_one, key_two, color="blue"):
    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    # Check if the key columns exist
    if key_one not in data.columns or key_two not in data.columns:
        raise ValueError(f"The data should have a {key_one} and {key_two} column")

    # Get all crossover indexes
    crossover_index = data[(data[key_one] <= data[key_two]) & (data[key_one].shift(1) >= data[key_two].shift(1))].index

    # Use .loc to get the corresponding 'Close' values
    crossover_close_values = data.loc[crossover_index, key_one]

    return go.Scatter(
        x=crossover_index,
        y=crossover_close_values,
        mode='markers',
        marker=dict(symbol='circle', size=10, color=color),
        name=f'{key_one} {key_two} Crossover'
    )

def create_peaks_chart(data: pd.DataFrame, key="Close", order = 5):

    # Check if the index is of type datetime
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("The index of the data should be of type datetime")

    keys = [f'{key}_highs', f'{key}_lows']

    for key_column in keys:
        if key_column not in data.columns:
            raise ValueError(f"The data should have a '{key_column}' column")

    # Get all peak indexes
    hh_close_index = data[data[f'{key}_highs'] == 1].index
    lh_close_index = data[data[f'{key}_highs'] == -1].index
    ll_close_index = data[data[f'{key}_lows'] == 1].index
    hl_close_index = data[data[f'{key}_lows'] == -1].index

    # Subtract for each index 10 hours
    # hh_close_index = hh_close_index - pd.Timedelta(hours=2 * order)
    # lh_close_index = lh_close_index - pd.Timedelta(hours=2 * order)
    # ll_close_index = ll_close_index - pd.Timedelta(hours=2 * order)
    # hl_close_index = hl_close_index - pd.Timedelta(hours=2 * order)
    # hh_close_index = hh_close_index
    # lh_close_index = lh_close_index
    # ll_close_index = ll_close_index
    # hl_close_index = hl_close_index

    # Use .loc to get the corresponding 'Close' values if the index is in the DataFrame
    hh_close_values = data.loc[hh_close_index, key]
    lh_close_values = data.loc[lh_close_index, key]
    ll_close_values = data.loc[ll_close_index, key]
    hl_close_values = data.loc[hl_close_index, key]

    # Add higher highs
    higher_high_graph = go.Scatter(
        x=hh_close_index,
        # x=dates[hh_close_index - order].values,
        y=hh_close_values,
        mode='markers',
        marker=dict(symbol='triangle-up', size=10, color='blue'),
        name='Higher High Confirmation'
    )

    # Add lower highs
    lower_high_graph = go.Scatter(
        x=lh_close_index,
        y=lh_close_values,
        mode='markers',
        marker=dict(symbol='triangle-down', size=10, color='red'),
        name='Lower High Confirmation'
    )

    # Add lower lows
    lower_lows_graph = go.Scatter(
        x=ll_close_index,
        y=ll_close_values,
        mode='markers',
        marker=dict(symbol='triangle-down', size=10, color='green'),
        name='Lower Lows Confirmation'
    )

    # Add higher lows
    higher_lows = go.Scatter(
        x=hl_close_index,
        y=hl_close_values,
        mode='markers',
        marker=dict(symbol='triangle-up', size=10, color='purple'),
        name='Higher Lows Confirmation'
    )

    return higher_high_graph, lower_high_graph, lower_lows_graph, higher_lows


def create_bullish_divergence_chart(data: pd.DataFrame, key_one, key_two, color = 'red'):
    """
    A bullish divergence occurs when the "<key_one>_lows" makes a new low but the "<key_two>_lows" makes a higher low.

    For example, if the RSI makes a new low but the close price makes a higher low, then we have a bullish divergence.
    """
    divergence_index = data[(data[f'{key_one}_lows'] == -1) & (data[f'{key_two}_lows'] == 1)].index
    divergence_close_values = data.loc[divergence_index, 'Close']

    return go.Scatter(
        x=divergence_index,
        y=divergence_close_values,
        mode='markers',
        marker=dict(symbol='circle', size=10, color=color),
        name='Bullish Divergence'
    )


def create_bearish_divergence_chart(data: pd.DataFrame, key_one, key_two, color = 'red'):
    """
    A bearish divergence occurs when the "<key_one>_highs" makes a new high but the "<key_two>_highs" makes a lower high.

    For example, if the RSI makes a new high but the close price makes a lower high, then we have a bearish divergence.
    """

    # Add divergence charts
    divergence_index = data[(data[f'{key_one}_highs'] == -1) & (data[f'{key_two}_highs'] == 1)].index
    divergence_close_values = data.loc[divergence_index, 'Close']

    return go.Scatter(
        x=divergence_index,
        y=divergence_close_values,
        mode='markers',
        marker=dict(symbol='circle', size=10, color=color),
        name='Bearish Divergence'
    )


def create_entry_graph(data: pd.DataFrame):


    # Iterate over each row in the DataFrame and check if there is a bullish divergence between the RSI and the close price
    # and if there is a crossover between the DI+ and DI- for the last 12 hours (6 candles)
    # Get all crossover indexes
    crossover_index = data[(data['+DI'] <= data['-DI']) & (data['+DI'].shift(1) >= data['-DI'].shift(1))].index
    data['di_crossover'] = 0
    data.loc[crossover_index, 'di_crossover'] = 1

    entry_indexes = []

    for row in data.itertuples():

        if row.di_crossover == 1:
            match = False
            # Check if there was a bullish divergence between the RSI and the close price in the last 2 days
            rsi_window = data.loc[row.Index - pd.Timedelta(days=2):row.Index, 'RSI_lows']
            close_window = data.loc[row.Index - pd.Timedelta(days=2):row.Index, 'Close_lows']

            # Go over each row and check if there is a bullish divergence between the RSI and the close price
            for rsi_row, close_row in zip(rsi_window, close_window):

                if rsi_row == -1 and close_row == 1:
                    entry_indexes.append(row.Index)
                    match = True
                    break

            if not match:
                # Check if the RSI had decreased
                rsi_window = data.loc[row.Index - pd.Timedelta(days=1):row.Index, 'RSI']
                rsi_diff = rsi_window.diff().mean()

                if rsi_diff < -2:
                    entry_indexes.append(row.Index)

        # If ema 50 <

            # # Check if there is a bullish divergence between the RSI and the close price
            # if row.Close_lows == 1 and row.RSI_lows == -1:
            #
            # # Check if there is a crossover in the last 12 hours
            # crossovers = data.loc[row.Index - pd.Timedelta(hours=12):row.Index, 'di_crossover']
            #
            # if crossovers.sum() > 0:
            #     entry_indexes.append(row.Index)

            # adx_window = data.loc[row.Index - pd.Timedelta(hours=4):row.Index, 'ADX']
            # rsi_window = data.loc[row.Index - pd.Timedelta(hours=4):row.Index, 'RSI']
            # adx_diff = adx_window.diff().mean()
            # rsi_diff = rsi_window.diff().mean()
            #
            # if adx_diff > -2 and adx_diff < 0:
            #     entry_indexes.append(row.Index)

    entry_close_values = data.loc[entry_indexes, 'Close']
    return go.Scatter(
        x=entry_indexes,
        y=entry_close_values,
        mode='markers',
        marker=dict(symbol='circle', size=10, color='green'),
        name='Entry Signal'
    )