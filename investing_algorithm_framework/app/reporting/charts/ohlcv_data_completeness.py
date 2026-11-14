import pandas as pd
from finterion_charts import ChartSpec, Marker, Price

from ._finterion_render import render_chart_html


def get_ohlcv_data_completeness_chart(
    df,
    timeframe='1min',
    windowsize=100,
    title="OHLCV Data completenes"
):
    df = df.copy()
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df = df.sort_values('Datetime').tail(windowsize)
    start = df['Datetime'].iloc[0]
    end = df['Datetime'].iloc[-1]
    freq = pd.to_timedelta(timeframe)
    expected = pd.date_range(start, end, freq=freq)
    actual = df['Datetime']
    missing = expected.difference(actual)

    # Calculte the percentage completeness
    completeness = len(actual) / len(expected) * 100
    title += f" ({completeness:.2f}% complete)"

    actual_ms = actual.astype("datetime64[ms]").astype("int64").to_numpy()
    flat = [1.0] * len(actual_ms)

    spec = ChartSpec(theme="finterion-light", grid="horizontal")
    spec.with_bars(time=actual_ms, open=flat, high=flat, low=flat, close=flat)
    spec.add_panel(
        Price(id="ohlcv_completeness", weight=1, title=title, type="line")
    )

    # Missing bars are plotted as red markers on the flat presence line.
    for ts in missing:
        spec.add_marker(Marker(
            time=ts.value // 1_000_000,
            side="sell",
            price=1.0,
            label="Missing",
        ))

    return render_chart_html(spec.validate(), height=300)
