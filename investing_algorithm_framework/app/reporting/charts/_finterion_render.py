"""Shared helpers for rendering ``finterion_charts.ChartSpec`` objects as
self-contained HTML, without requiring IPython or network access.

``finterion_charts`` ships an offline embed bundle (``_static/embed.html``)
inside its wheel. We inject the spec JSON into that bundle and wrap it in an
``<iframe srcdoc="...">`` so the resulting HTML has no external/CDN
dependency, mirroring how the rest of the backtest report is generated.
"""
import json


_SPEC_PLACEHOLDER = "/*__FINTERION_SPEC_JSON__*/ null"


def _css_size(value):
    return f"{int(value)}px" if isinstance(value, int) else str(value)


def render_chart_html(spec, width="100%", height=420):
    """Render a ``ChartSpec`` (or its dict form) as a self-contained iframe."""
    from importlib.resources import files
    from finterion_charts import ChartSpec

    spec_dict = spec.to_dict() if isinstance(spec, ChartSpec) else spec

    html = files("finterion_charts").joinpath(
        "_static", "embed.html"
    ).read_text(encoding="utf-8")

    if _SPEC_PLACEHOLDER not in html:
        raise RuntimeError(
            "finterion-charts embed bundle is missing the spec placeholder; "
            "check the installed finterion-charts version."
        )

    spec_json = json.dumps(
        spec_dict, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).replace("</", "<\\/")
    html = html.replace(_SPEC_PLACEHOLDER, spec_json)
    srcdoc = html.replace("&", "&amp;").replace('"', "&quot;")

    return (
        f'<iframe srcdoc="{srcdoc}" '
        f'style="width:{_css_size(width)};height:{_css_size(height)};'
        'border:0;display:block;background:transparent;" '
        'sandbox="allow-scripts" loading="lazy"></iframe>'
    )


class FinterionChart:
    """Drop-in replacement for a plotly ``Figure``.

    Wraps a ``ChartSpec`` and exposes a ``to_html()`` method with the same
    call signature legacy callers used for plotly figures, so existing
    ``fig.to_html(full_html=False, include_plotlyjs='cdn', ...)`` call sites
    keep working unchanged (plotly-only kwargs are accepted and ignored).
    """

    def __init__(self, spec, height=420):
        self.spec = spec
        self.height = height

    def to_html(
        self, full_html=False, include_plotlyjs=None,
        config=None, default_width=None, width=None, height=None
    ):
        return render_chart_html(
            self.spec,
            width=width or default_width or "100%",
            height=height or self.height,
        )
