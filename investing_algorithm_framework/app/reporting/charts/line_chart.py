import plotly.graph_objects as go


def create_line_scatter(x, y, name, colour = 'blue'):
    return go.Scatter(
        x=x,
        y=y,
        mode='lines',
        name=name,
        line=dict(color=colour)
    )
