import pandas as pd
import plotly.graph_objects as go


def get_rolling_sharpe_ratio_chart(rolling_sharpe_ratio_series):
    """
    Generates a Plotly figure showing the rolling Sharpe ratio series.

    Args:
        rolling_sharpe_ratio_series: List of tuples with rolling Sharpe
            ratio data. Each tuple should contain a Sharpe ratio
            value and the corresponding timestamp.
    Returns:
        plotly.graph_objects.Figure: A Plotly figure containing
        the rolling Sharpe ratio chart.
    """
    results = rolling_sharpe_ratio_series
    rolling_sharpe_ratio_df = pd.DataFrame(
        results, columns=['sharpe_ratio', 'timestamp']
    )
    rolling_sharpe_ratio_df['timestamp'] = pd.to_datetime(
        rolling_sharpe_ratio_df['timestamp']
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rolling_sharpe_ratio_df['timestamp'],
            y=rolling_sharpe_ratio_df['sharpe_ratio'],
            mode='lines',
            name='Rolling Sharpe Ratio',
            line=dict(color='#1f77b4', width=2)
        )
    )

    last_nan_row = rolling_sharpe_ratio_df[
        rolling_sharpe_ratio_df['sharpe_ratio'].isna()
    ]
    if not last_nan_row.empty:
        last_nan_date = last_nan_row['timestamp'].max()
        fig.add_vline(
            x=last_nan_date,
            line=dict(color='grey', width=1, dash='dash')
        )

    fig.update_layout(
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            tickformat='%b %Y',
            tickfont=dict(color='black'),
            showline=True,
            linecolor='black',
            ticks='outside',
            tickcolor='black'
        ),
        yaxis=dict(
            title='Rolling Sharpe Ratio',
            showgrid=True,
            gridcolor='lightgray',
            tickfont=dict(color='black'),
            showline=True,
            linecolor='black',
            ticks='outside',
            tickcolor='black'
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black'),
        hovermode='x unified',
        legend=dict(
            font=dict(color='black'),
            bgcolor='rgba(0,0,0,0)',
            bordercolor='black'
        ),
        height=300,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    return fig
