import pandas as pd
from finterion_charts import ChartSpec, Marker, Price

from ._finterion_render import FinterionChart


def get_entry_and_exit_signals(
    entry_signals: pd.Series,
    exit_signals: pd.Series,
    price_data: pd.DataFrame
):
    """
    Plots the price chart with entry and exit signals.

    Args:
        entry_signals (pd.Series): Series containing buy
            signals with datetime index. Entry signals should
            be boolean values.
        exit_signals (pd.Series): Series containing exit signals
            with datetime index. Exit signals should be boolean values.
        price_data (pd.DataFrame): DataFrame containing price
            data with datetime index and 'Close'

    Returns:
        FinterionChart: A chart wrapper with the price chart and
        entry/exit signal markers, renderable via ``.to_html()``.
    """
    close = price_data["Close"].to_numpy()
    time_ms = pd.to_datetime(price_data.index) \
        .astype("datetime64[ms]").astype("int64").to_numpy()

    spec = ChartSpec(theme="finterion-light", grid="horizontal")
    spec.with_bars(time=time_ms, open=close, high=close, low=close, close=close)
    spec.add_panel(
        Price(id="price", weight=1, title="Entry and Exit Signals", type="line")
    )

    for ts, price in price_data.loc[entry_signals, "Close"].items():
        spec.add_marker(Marker(
            time=pd.Timestamp(ts).value // 1_000_000,
            side="buy",
            price=float(price),
            label="Entry",
        ))

    for ts, price in price_data.loc[exit_signals, "Close"].items():
        spec.add_marker(Marker(
            time=pd.Timestamp(ts).value // 1_000_000,
            side="sell",
            price=float(price),
            label="Exit",
        ))

    return FinterionChart(spec.validate(), height=600)
