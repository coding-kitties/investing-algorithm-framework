import pandas as pd
import plotly.graph_objects as go


def get_entry_and_exit_signals(
    entry_signals: pd.Series,
    exit_signals: pd.Series,
    price_data: pd.DataFrame
):
    """
    Plots the price chart with entry and exit signals.

    Args:
        entry_signals (pd.Series): Series containing buy
            signals with datetime index. Entry signals should
            be boolean values.
        exit_signals (pd.Series): Series containing exit signals
            with datetime index. Exit signals should be boolean values.
        price_data (pd.DataFrame): DataFrame containing price
            data with datetime index and 'Close'

    Returns:
        go.Figure: Plotly figure with price chart and signals.
    """
    # Create the base candlestick or line chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=price_data.index,
        y=price_data["Close"],
        mode="lines",
        name="Close Price",
        line=dict(color="blue")
    ))

    # Entry points
    entry_points = price_data[entry_signals]
    fig.add_trace(go.Scatter(
        x=entry_points.index,
        y=entry_points["Close"],
        mode="markers",
        name="Entry",
        marker=dict(symbol="triangle-up", color="green", size=10)
    ))

    # Exit points
    exit_points = price_data[exit_signals]
    fig.add_trace(go.Scatter(
        x=exit_points.index,
        y=exit_points["Close"],
        mode="markers",
        name="Exit",
        marker=dict(symbol="triangle-down", color="red", size=10)
    ))

    # Layout settings
    fig.update_layout(
        title="Entry and Exit Signals",
        xaxis_title="Date",
        yaxis_title="Price",
        legend=dict(x=0, y=1),
        height=600,
        template="plotly_white"
    )

    return fig
