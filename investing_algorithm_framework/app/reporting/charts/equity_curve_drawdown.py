import pandas as pd
from finterion_charts import ChartSpec, Indicator

from ._finterion_render import FinterionChart


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

    # Equity curve and drawdown series are derived from the same portfolio
    # snapshots, so they share the same timestamps/length.
    equity_values = equity_curve_df["value"].to_numpy()
    time_ms = pd.to_datetime(equity_curve_df["datetime"]) \
        .astype("datetime64[ms]").astype("int64").to_numpy()
    drawdown_values = drawdown_df["value"].to_numpy()

    spec = ChartSpec(theme="finterion-light", grid="horizontal")
    spec.with_bars(
        time=time_ms, open=equity_values, high=equity_values,
        low=equity_values, close=equity_values,
    )
    spec.with_column("equity", equity_values)
    spec.with_column("drawdown", drawdown_values)
    spec.add_panel(Indicator.panel(
        id="equity",
        weight=0.7,
        values="equity",
        kind="line",
        color="#10b981",
        title="Equity Curve",
    ))
    spec.add_panel(Indicator.panel(
        id="drawdown",
        weight=0.3,
        values="drawdown",
        kind="area",
        color="#ef4444",
        title="Drawdown",
    ))

    return FinterionChart(spec.validate(), height=600)
