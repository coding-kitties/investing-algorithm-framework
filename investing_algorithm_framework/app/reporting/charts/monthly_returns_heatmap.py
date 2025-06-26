import pandas as pd
import plotly.graph_objects as go


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

    z = pivot_df.values
    text = [
        [f"{v * 100:.2f}%" if pd.notna(v) else "" for v in row] for row in z
    ]
    hover_template = "Year %{y}<br>Month %{x}<br>" + \
        "Return: %{z:.2%}<extra></extra>"
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=pivot_df.columns,
        y=pivot_df.index,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 12},
        colorscale="RdYlGn",
        showscale=False,
        hovertemplate=hover_template,
        zmin=-0.1,
        zmax=0.1
    ))

    fig.update_layout(
        title="Monthly Returns Heatmap (%)",
        xaxis_title="Month",
        yaxis=dict(
            title=None,
            tickmode='array',
            tickvals=list(pivot_df.index),
            ticktext=[str(year) for year in pivot_df.index],
            autorange=True  # Remove 'reversed' to match ascending order
        ),
        template="plotly_white",
        margin=dict(l=0, r=0, t=40, b=20),
        height=350,
        showlegend=False
    )
    return fig
