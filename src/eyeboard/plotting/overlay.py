"""Draw two datasets on one figure: A as it is, B dashed in the same colors."""

import plotly.colors
import plotly.graph_objects as go

_SCATTER_TYPES = ("scatter", "scattergl")
B_SUFFIX = " (B)"
A_SUFFIX = " (A)"


def _colorway(fig: go.Figure) -> list[str]:
    template = fig.layout.template
    colors = template.layout.colorway if template and template.layout else None
    return list(colors or plotly.colors.qualitative.Plotly)


def _trace_color(trace) -> str | None:
    """The color a trace was given explicitly, if any."""
    if trace.type in _SCATTER_TYPES:
        line_color = trace.line.color if trace.line else None
        marker_color = trace.marker.color if trace.marker else None
        return line_color or marker_color
    return trace.marker.color if trace.marker else None


def _set_color(trace, color: str) -> None:
    if trace.type in _SCATTER_TYPES:
        trace.update(line={"color": color}, marker={"color": color})
    else:
        trace.update(marker={"color": color})


def overlay_figures(fig_a: go.Figure, fig_b: go.Figure) -> go.Figure:
    """Return A's figure with B's traces added.

    Series that exist in both keep one color (B takes A's); B is drawn dashed
    (lines), as crosses (markers) or faded (bars), and names end with (A) / (B).
    The inputs are not modified.
    """
    result = go.Figure(fig_a)
    palette = _colorway(result)

    colors: dict[str, str] = {}
    for index, trace in enumerate(result.data):
        base = trace.name or f"series {index}"
        color = _trace_color(trace) or palette[len(colors) % len(palette)]
        colors.setdefault(base, color)
        _set_color(trace, color)
        trace.name = base + A_SUFFIX
        trace.legendgroup = base

    for index, source in enumerate(fig_b.data):
        base = source.name or f"series {index}"
        trace = go.Figure(source).data[0]
        if base not in colors:
            colors[base] = palette[len(colors) % len(palette)]
        _set_color(trace, colors[base])
        if trace.type in _SCATTER_TYPES:
            if trace.mode and "lines" in trace.mode:
                trace.update(line={"dash": "dash"})
            else:
                trace.update(marker={"symbol": "x"})
        else:
            trace.update(marker={"opacity": 0.55})
        trace.name = base + B_SUFFIX
        trace.legendgroup = base
        result.add_trace(trace)
    return result
