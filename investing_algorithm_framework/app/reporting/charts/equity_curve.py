import pandas as pd
from plotly import graph_objects as go


def get_equity_curve_chart(equity_curve_series):
    equity_curve_df = pd.DataFrame(
        equity_curve_series, columns=["value", "datetime"]
    )

    # Normalize equity to start at 1
    equity_curve_df["value"] = (
        equity_curve_df["value"] / equity_curve_df["value"].iloc[0]
    )

    fig = go.Figure()

    # Draw equity curve
    fig.add_trace(
        go.Scatter(
            x=equity_curve_df["datetime"],
            y=equity_curve_df["value"],
            mode="lines",
            line=dict(color="rgba(0, 128, 0, 0.8)", width=1),
            name="Equity Curve",
            hovertemplate="<b>Equity</b><br>%{x}<br>Value: %{y:.2f}<extra></extra>"
        )
    )

    fig.update_layout(
        xaxis=dict(title=None),
        yaxis=dict(title="Cumulative Equity (log)", type="log"),
        title="Equity Curve with Drawdown",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig
