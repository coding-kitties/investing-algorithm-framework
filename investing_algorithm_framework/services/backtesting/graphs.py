from typing import List

import pandas as pd
from plotly import graph_objects as go

from investing_algorithm_framework.domain import Trade


def create_prices_chart(df, column="Close"):
    """
    Function to create a prices chart.
    """
    return go.Scatter(
        x=df.index,
        y=df[column],
        mode='lines',
        line=dict(color="blue", width=1),
        name="Close"
    )


def create_trade_entry_markers_chart(df, trades: List[Trade]):
    df['entry_prices'] = None

    for trade in trades:
        opened_index = df.index.get_indexer(
            [pd.to_datetime(trade.opened_at)], method='nearest'
        )
        df.at[df.index[opened_index[0]], 'entry_prices'] = df.at[
            df.index[opened_index[0]], 'Close']

    return go.Scatter(
        x=df.index,
        y=df["entry_prices"],
        marker_symbol="arrow-up",
        marker=dict(color='green'),
        mode='markers',
        name='Buy'
    )


def create_trade_exit_markers_chart(df, trades: List[Trade]):
    df['exit_prices'] = None

    for trade in trades:

        if trade.closed_at is not None:
            closed_index = df.index.get_indexer(
                [pd.to_datetime(trade.closed_at)], method='nearest'
            )
            df.at[df.index[closed_index[0]], 'exit_prices'] = df.at[
                df.index[closed_index[0]], 'Close']

    return go.Scatter(
        x=df.index,
        y=df["exit_prices"],
        marker_symbol="arrow-down",
        marker=dict(color='red'),
        mode='markers',
        name='Sell'
    )
