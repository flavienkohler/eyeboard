"""Build a Plotly figure from a prepared table and a plot specification.

Every plot type, with or without a secondary axis and with or without a
"color by" column, goes through the same code: one trace per series (and per
group), assigned to the primary or the secondary Y axis.
"""

import pandas as pd
import plotly.graph_objects as go

from eyeboard.dashboards.model import PlotSpec, SeriesStyle

# Above this many points a trace is drawn with WebGL, which stays smooth with
# hundreds of thousands of points. Below it SVG is used: it looks crisper and a
# page can only hold a limited number of WebGL canvases.
WEBGL_MIN_POINTS = 5_000

PRIMARY_AXIS = "y"
SECONDARY_AXIS = "y2"
EMPTY_GROUP_LABEL = "(empty)"
# Room above the plot for a title and a legend of up to two rows (overlays have two).
TITLED_TOP_MARGIN = 85


def _groups(
    df: pd.DataFrame, color_col: str | None
) -> list[tuple[str | None, pd.DataFrame]]:
    """Split the table by the "color by" column; one group when there is none."""
    if not color_col:
        return [(None, df)]
    return [
        (EMPTY_GROUP_LABEL if pd.isna(key) else str(key), part)
        for key, part in df.groupby(color_col, sort=False, dropna=False)
    ]


def _axis_title(custom: str | None, columns: list[str]) -> str | None:
    """Use the title given by the user, else the series name if it is unambiguous."""
    if custom:
        return custom
    return columns[0] if len(columns) == 1 else None


def make_trace(
    plot_type: str,
    *,
    x: pd.Series,
    y: pd.Series,
    name: str,
    axis: str,
    style: SeriesStyle,
    color_by_group: bool,
) -> go.Scatter | go.Scattergl | go.Bar:
    """Create the trace of one series (or one group of a series)."""
    # With a "color by" column the traces are told apart by the palette, so a
    # single fixed series color would paint every group the same.
    color = None if color_by_group else style.color
    base = {"x": x, "y": y, "name": name, "yaxis": axis}
    line = {"color": color, "width": style.width, "dash": style.dash}
    scatter = go.Scattergl if len(x) > WEBGL_MIN_POINTS else go.Scatter

    if plot_type == "Bar":
        return go.Bar(**base, marker={"color": color})
    if plot_type == "Scatter":
        return scatter(**base, mode="markers", marker={"color": color})
    if plot_type == "Area":
        # WebGL cannot fill, so areas always use SVG.
        return go.Scatter(**base, mode="lines", fill="tozeroy", line=line)
    return scatter(**base, mode="lines", line=line)


def make_figure(df: pd.DataFrame, spec: PlotSpec) -> go.Figure:
    """Create the figure of a plot specification from its prepared table."""
    fig = go.Figure()
    if spec.theme != "none":
        fig.update_layout(template=spec.theme)

    series = [(column, PRIMARY_AXIS) for column in spec.y_cols] + [
        (column, SECONDARY_AXIS) for column in spec.y2_cols
    ]
    groups = _groups(df, spec.color_col)
    for column, axis in series:
        style = spec.series_style.get(column) or SeriesStyle()
        for group, part in groups:
            name = column if group is None else f"{column} · {group}"
            if axis == SECONDARY_AXIS:
                name += " (Y2)"
            fig.add_trace(
                make_trace(
                    spec.plot_type,
                    x=part[spec.x_col],
                    y=part[column],
                    name=name,
                    axis=axis,
                    style=style,
                    color_by_group=group is not None,
                )
            )

    fig.update_layout(
        margin={
            "l": 10,
            "r": 10,
            "t": TITLED_TOP_MARGIN if spec.title else 20,
            "b": 10,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
        xaxis={"title": spec.x_col},
        yaxis={"title": _axis_title(spec.yaxis_title_1, spec.y_cols)},
        barmode="group",
    )
    if spec.title:
        # Top left, above the legend, which sits just over the plot area.
        fig.update_layout(
            title={"text": spec.title, "x": 0, "y": 0.99, "yanchor": "top"}
        )
    if spec.y2_cols:
        fig.update_layout(
            yaxis2={
                "title": _axis_title(spec.yaxis_title_2, spec.y2_cols),
                "overlaying": PRIMARY_AXIS,
                "side": "right",
            }
        )
    return fig
