import pandas as pd
from plotly.subplots import make_subplots
from plotly import graph_objects as go


def get_equity_curve_with_drawdown_chart(equity_curve_series, drawdown_series):
    equity_curve_df = pd.DataFrame(
        equity_curve_series, columns=["value", "datetime"]
    )
    drawdown_df = pd.DataFrame(
        drawdown_series, columns=["value", "datetime"]
    )

    # Normalize equity to start at 1
    equity_curve_df["value"] = (
        equity_curve_df["value"] / equity_curve_df["value"].iloc[0]
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=["", ""]
    )

    # Draw equity curve
    fig.add_trace(
        go.Scatter(
            x=equity_curve_df["datetime"],
            y=equity_curve_df["value"],
            mode="lines",
            line=dict(color="rgba(0, 128, 0, 0.8)", width=1),
            name="Equity Curve",
            hovertemplate="<b>Equity</b><br>%{x}<br>Value: %{y:.2f}<extra></extra>"
        ),
        row=1,
        col=1
    )

    # Drawdown area
    fig.add_trace(
        go.Scatter(
            x=drawdown_df["datetime"],
            y=drawdown_df["value"],
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(255, 99, 71, 0.3)",
            line=dict(color="rgba(255, 99, 71, 0.8)", width=1),
            name="Drawdown"
        ),
        row=2,
        col=1
    )

    # Final layout
    fig.update_layout(
        xaxis=dict(title=None),
        yaxis=dict(title="Cumulative Equity (log)", type="log"),
        xaxis2=dict(title=None),
        yaxis2=dict(
            title="Drawdown",
            tickformat=".0%",
            tickvals=[-0.2, -0.15, -0.1, -0.05, 0]  # Clean % ticks
        ),
        template="plotly_white",
        height=600,
        showlegend=False,
        hovermode="x unified",  # Enables vertical hover line
        margin=dict(l=0, r=0, t=0, b=0),
    )

    return fig
