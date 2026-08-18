import pandas as pd
from finterion_charts import ChartSpec, VBar

from ._finterion_render import FinterionChart


def get_yearly_returns_bar_chart(yearly_returns_series):
    """
    Create a bar chart showing yearly returns.
    This chart visualizes the yearly returns of the backtest report.

    Args:
        yearly_returns_series: The yearly returns data as a series.

    Returns:
        FinterionChart: A chart wrapper containing the yearly returns bar
        chart, renderable via ``.to_html()``.
    """
    # Convert the series to a DataFrame
    df = pd.DataFrame(yearly_returns_series, columns=["Return", "Year"])

    # Ensure the 'Year' column is datetime-like
    df["Year"] = pd.to_datetime(df["Year"], errors="coerce")

    # Extract the year from the datetime
    df["Year"] = df["Year"].dt.year

    spec = ChartSpec(theme="finterion-light")
    spec.add_panel(VBar(
        id="yearly_returns",
        weight=1,
        title="Yearly Returns (%)",
        categories=[str(year) for year in df["Year"]],
        values=df["Return"].to_numpy(),
        positive_color="#10b981",
        negative_color="#ef4444",
        format="pct0",
    ))

    return FinterionChart(spec.validate(), height=350)
