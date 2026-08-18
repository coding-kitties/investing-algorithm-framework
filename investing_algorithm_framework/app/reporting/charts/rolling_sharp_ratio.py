import numpy as np
import pandas as pd
from finterion_charts import ChartSpec, Indicator

from ._finterion_render import FinterionChart


def get_rolling_sharpe_ratio_chart(rolling_sharpe_ratio_series):
    """
    Generates a finterion-charts ChartSpec showing the rolling Sharpe
    ratio series.

    Args:
        rolling_sharpe_ratio_series: List of tuples with rolling Sharpe
            ratio data. Each tuple should contain a Sharpe ratio
            value and the corresponding timestamp.
    Returns:
        FinterionChart: A chart wrapper containing the rolling Sharpe
        ratio chart, renderable via ``.to_html()``.
    """
    results = rolling_sharpe_ratio_series
    rolling_sharpe_ratio_df = pd.DataFrame(
        results, columns=['sharpe_ratio', 'timestamp']
    )
    rolling_sharpe_ratio_df['timestamp'] = pd.to_datetime(
        rolling_sharpe_ratio_df['timestamp']
    )

    time_ms = rolling_sharpe_ratio_df['timestamp'] \
        .astype("datetime64[ms]").astype("int64").to_numpy()
    # Bars can't hold NaN (warmup period); the Sharpe values themselves
    # (with NaN preserved as a gap) go in a column instead.
    flat = np.ones(len(time_ms))
    sharpe_values = rolling_sharpe_ratio_df['sharpe_ratio'].to_numpy()

    spec = ChartSpec(theme="finterion-light", grid="horizontal")
    spec.with_bars(time=time_ms, open=flat, high=flat, low=flat, close=flat)
    spec.with_column("sharpe", sharpe_values)
    spec.add_panel(Indicator.panel(
        id="sharpe",
        weight=1,
        values="sharpe",
        kind="line",
        color="#1f77b4",
        title="Rolling Sharpe Ratio",
        ref_lines=[0],
    ))

    return FinterionChart(spec.validate(), height=300)
