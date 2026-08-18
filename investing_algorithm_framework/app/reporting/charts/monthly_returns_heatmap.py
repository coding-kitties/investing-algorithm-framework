import pandas as pd
from finterion_charts import ChartSpec, Heatmap

from ._finterion_render import FinterionChart


def get_monthly_returns_heatmap_chart(monthly_return_series):
    df = pd.DataFrame(monthly_return_series, columns=["Return", "Timestamp"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
    df["Year"] = df["Timestamp"].dt.year
    df["Month"] = df["Timestamp"].dt.strftime("%b")

    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    df["Month"] = pd.Categorical(
        df["Month"], categories=month_order, ordered=True
    )

    # Ensure all months are present for each year
    all_years = df["Year"].unique()
    all_months = pd.DataFrame(
        [(year, month) for year in all_years for month in month_order],
        columns=["Year", "Month"]
    )
    df = pd.merge(
        all_months,
        df,
        on=["Year", "Month"],
        how="left"
    ).fillna({"Return": 0.0})

    # Pivot to matrix form
    pivot_df = df.pivot(index="Year", columns="Month", values="Return")
    pivot_df = pivot_df.reindex(columns=month_order)
    pivot_df = pivot_df.sort_index(ascending=True)  # Change to ascending order

    spec = ChartSpec(theme="finterion-light")
    spec.add_panel(Heatmap(
        id="monthly_returns",
        weight=1,
        title="Monthly Returns Heatmap (%)",
        rows=[str(year) for year in pivot_df.index],
        cols=list(pivot_df.columns),
        values=pivot_df.values.tolist(),
        format="pct2",
        range=0.1,
        color_scale=("#ef4444", "#f8fafc", "#10b981"),
    ))

    return FinterionChart(spec.validate(), height=350)
