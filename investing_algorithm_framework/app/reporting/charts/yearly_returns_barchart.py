import pandas as pd
import plotly.express as px


def get_yearly_returns_bar_chart(yearly_returns_series):
    """
    Create a bar chart showing yearly returns.
    This chart visualizes the yearly returns of the backtest report.

    Args:
        yearly_returns_series: The yearly returns data as a series.

    Returns:
        A Plotly Figure object representing the yearly returns bar chart.
    """
    # Convert the series to a DataFrame
    df = pd.DataFrame(yearly_returns_series, columns=["Return", "Year"])

    # Ensure the 'Year' column is datetime-like
    df["Year"] = pd.to_datetime(df["Year"], errors="coerce")

    # Extract the year from the datetime
    df["Year"] = df["Year"].dt.year

    # Convert returns to percentage
    df["Return"] = df["Return"] * 100  # Convert to percentage

    # Ensure that there are no floating point numbers in the Return column
    df["Return"] = df["Return"].round(0).astype(int)

    # Create the bar chart
    fig = px.bar(
        df,
        x="Year",
        y="Return",
        text="Return",
        title="Yearly Returns (%)",
        color="Return",
        color_continuous_scale=["red", "green"]
    )

    # Update layout for padding and formatting
    fig.update_layout(
        xaxis=dict(title="Time", tickmode="linear"),
        yaxis=dict(title=None, tickformat="", range=[-10, 30]),
        showlegend=False,
        coloraxis_showscale=False,  # Disable the color scale legend
        height=350,
        margin=dict(l=0, r=0, t=40, b=20),
    )

    # Format bar text
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    return fig

