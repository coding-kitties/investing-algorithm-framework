import plotly.graph_objects as go
import pandas as pd
import plotly.io as pio

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
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=actual,
            y=[1]*len(actual),
            mode='markers',
            name='Present',
            marker=dict(color='green', size=6)
        )
    )
    fig.add_trace(
        go.Scatter(
            x=missing,
            y=[1]*len(missing),
            mode='markers',
            name='Missing',
            marker=dict(color='red', size=6, symbol='x')
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title='Datetime',
        yaxis=dict(showticklabels=False),
        height=300,
        showlegend=True
    )

    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
