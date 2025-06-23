import pandas as pd
from plotly.subplots import make_subplots
from plotly import graph_objects as go


def get_equity_curve_with_drawdown_chart(equity_curve_series, drawdown_series):
    equity_curve_df = pd.DataFrame(
        equity_curve_series, columns=["datetime", "value"]
    )
    drawdown_df = pd.DataFrame(
        drawdown_series, columns=["datetime", "value"]
    )

    # Normalize equity to start at 1
    equity_curve_df["value"] = (equity_curve_df["value"] /
                                equity_curve_df["value"].iloc[0])

    # Split into above and below 1
    above_1 = equity_curve_df[equity_curve_df["value"] >= 1]
    below_1 = equity_curve_df[equity_curve_df["value"] < 1]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=["", ""]
    )

    # Equity curve - gains (green)
    fig.add_trace(
        go.Scatter(
            x=above_1["datetime"],
            y=above_1["value"],
            mode="lines",
            line=dict(color="rgba(34, 139, 34, 0.9)", width=1.5),
            name="Cumulative Equity (Gains)"
        ),
        row=1,
        col=1
    )

    # Equity curve - losses (red)
    fig.add_trace(
        go.Scatter(
            x=below_1["datetime"],
            y=below_1["value"],
            mode="lines",
            line=dict(color="rgba(220, 20, 60, 0.9)", width=1.5),
            name="Cumulative Equity (Loss)"
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
