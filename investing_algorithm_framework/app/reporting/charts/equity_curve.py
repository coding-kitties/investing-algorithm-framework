import pandas as pd
from finterion_charts import ChartSpec, Indicator

from ._finterion_render import FinterionChart


def _time_ms(datetimes):
    idx = pd.to_datetime(pd.Series(list(datetimes)))
    return idx.astype("datetime64[ms]").astype("int64").to_numpy()


def get_equity_curve_chart(equity_curve_series):
    equity_curve_df = pd.DataFrame(
        equity_curve_series, columns=["value", "datetime"]
    )

    # Normalize equity to start at 1
    equity_curve_df["value"] = (
        equity_curve_df["value"] / equity_curve_df["value"].iloc[0]
    )
    values = equity_curve_df["value"].to_numpy()
    time_ms = _time_ms(equity_curve_df["datetime"])

    spec = ChartSpec(theme="finterion-light", grid="horizontal")
    spec.with_bars(
        time=time_ms, open=values, high=values, low=values, close=values
    )
    spec.with_column("equity", values)
    spec.add_panel(Indicator.panel(
        id="equity",
        weight=1,
        values="equity",
        kind="line",
        color="#10b981",
        title="Equity Curve",
    ))

    return FinterionChart(spec.validate())
