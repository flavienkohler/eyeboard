"""Figure creation and rendering helpers."""

import logging
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_object_dtype

from plot_studio.services.columns import resolve_column

LOGGER = logging.getLogger(__name__)
COLUMN_PREVIEW_MAX_POINTS = 300


def to_numeric_safe(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert object columns to numeric where possible without raising."""
    numeric_df = df.copy()
    for col in cols:
        if col in numeric_df.columns and is_object_dtype(numeric_df[col]):
            try:
                numeric_df[col] = pd.to_numeric(numeric_df[col])
            except (TypeError, ValueError):
                continue
    return numeric_df


def apply_axis_titles(
    fig: go.Figure,
    title_y1: str | None = None,
    title_y2: str | None = None,
) -> None:
    """Apply optional axis titles to a figure."""
    updates: dict[str, Any] = {}
    if title_y1:
        updates["yaxis"] = {"title": title_y1}
    if title_y2:
        updates["yaxis2"] = {"title": title_y2}
    if updates:
        fig.update_layout(**updates)


def apply_series_styles(
    fig: go.Figure,
    series_style: dict[str, dict[str, Any]],
) -> None:
    """Apply per-trace styling to a Plotly figure."""
    if not series_style:
        return

    for trace in fig.data:
        name = getattr(trace, "name", None)
        if not name:
            continue

        style = series_style.get(name)
        if style is None and name.endswith(" (Y2)"):
            style = series_style.get(name[:-5])
        if not style:
            continue

        color = style.get("color")
        width = style.get("width")
        dash = style.get("dash")

        if hasattr(trace, "line"):
            line_updates: dict[str, Any] = {}
            if color:
                line_updates["color"] = color
            if isinstance(width, (int, float)):
                line_updates["width"] = float(width)
            if dash:
                line_updates["dash"] = dash
            if line_updates:
                trace.update(line=line_updates)

        if hasattr(trace, "marker") and color:
            try:
                trace.update(marker={"color": color})
            except Exception:
                pass

        if trace.type == "bar" and color:
            try:
                trace.update(marker={"color": color})
            except Exception:
                pass


def make_figure(df: pd.DataFrame, spec: dict[str, Any]) -> go.Figure:
    """Create a Plotly figure based on a plot specification."""
    x_col = spec.get("x_col")
    y_cols = spec.get("y_cols") or []
    y2_cols = spec.get("y2_cols") or []
    plot_type = spec.get("plot_type", "Line")
    template = spec.get("template", "plotly")
    title = spec.get("title") or None
    color_col = spec.get("color_col") or None
    agg = spec.get("agg") or None
    series_style = spec.get("series_style") or {}

    plot_df = df
    if agg and x_col and (y_cols or y2_cols):
        agg_cols = list(dict.fromkeys(y_cols + y2_cols))
        try:
            grouped = plot_df.groupby(x_col, dropna=False)[agg_cols]
            if agg == "mean":
                plot_df = grouped.mean(numeric_only=True).reset_index()
            elif agg == "sum":
                plot_df = grouped.sum(numeric_only=True).reset_index()
            elif agg == "min":
                plot_df = grouped.min(numeric_only=True).reset_index()
            elif agg == "max":
                plot_df = grouped.max(numeric_only=True).reset_index()
            elif agg == "median":
                plot_df = grouped.median(numeric_only=True).reset_index()
        except Exception:
            plot_df = df

    plot_df = to_numeric_safe(plot_df, list(dict.fromkeys(y_cols + y2_cols)))

    if not y2_cols:
        template_name = template if template != "none" else None
        if plot_type == "Line":
            fig = px.line(
                plot_df,
                x=x_col,
                y=y_cols,
                color=color_col,
                template=template_name,
                title=title,
            )
        elif plot_type == "Scatter":
            fig = px.scatter(
                plot_df,
                x=x_col,
                y=y_cols,
                color=color_col,
                template=template_name,
                title=title,
            )
        elif plot_type == "Bar":
            fig = px.bar(
                plot_df,
                x=x_col,
                y=y_cols,
                color=color_col,
                template=template_name,
                title=title,
            )
        elif plot_type == "Area":
            fig = px.area(
                plot_df,
                x=x_col,
                y=y_cols,
                color=color_col,
                template=template_name,
                title=title,
            )
        else:
            fig = px.line(
                plot_df,
                x=x_col,
                y=y_cols,
                color=color_col,
                template=template_name,
                title=title,
            )
        apply_axis_titles(fig, spec.get("yaxis_title_1"), None)
        apply_series_styles(fig, series_style)
        fig.update_layout(margin={"l": 10, "r": 10, "t": 50 if title else 20, "b": 10})
        return fig

    fig = go.Figure()
    if template != "none":
        fig.update_layout(template=template)
    if title:
        fig.update_layout(title=title)

    for col in y_cols:
        style = series_style.get(col, {})
        if plot_type in ("Line", "Area"):
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    mode="lines",
                    name=col,
                    yaxis="y1",
                    line={
                        "color": style.get("color") or None,
                        "width": float(style.get("width"))
                        if isinstance(style.get("width"), (int, float))
                        else None,
                        "dash": style.get("dash") or None,
                    },
                )
            )
        elif plot_type == "Scatter":
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    mode="markers",
                    name=col,
                    yaxis="y1",
                    marker={"color": style.get("color") or None},
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    name=col,
                    yaxis="y1",
                    marker={"color": style.get("color") or None},
                )
            )

    for col in y2_cols:
        style = series_style.get(col, {})
        trace_name = f"{col} (Y2)"
        if plot_type in ("Line", "Area"):
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    mode="lines",
                    name=trace_name,
                    yaxis="y2",
                    line={
                        "color": style.get("color") or None,
                        "width": float(style.get("width"))
                        if isinstance(style.get("width"), (int, float))
                        else None,
                        "dash": style.get("dash") or None,
                    },
                )
            )
        elif plot_type == "Scatter":
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    mode="markers",
                    name=trace_name,
                    yaxis="y2",
                    marker={"color": style.get("color") or None},
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=plot_df[x_col],
                    y=plot_df[col],
                    name=trace_name,
                    yaxis="y2",
                    marker={"color": style.get("color") or None},
                )
            )

    fig.update_layout(
        yaxis={"title": spec.get("yaxis_title_1") or None},
        yaxis2={
            "title": spec.get("yaxis_title_2") or None,
            "overlaying": "y",
            "side": "right",
        },
        margin={"l": 10, "r": 10, "t": 50 if title else 20, "b": 10},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    return fig


def render_plot_from_spec(
    df: pd.DataFrame,
    spec: dict[str, Any],
    available_cols: list[str],
) -> tuple[go.Figure | None, list[str]]:
    """Resolve columns and render a figure for the current dataframe."""
    resolution_warnings: list[str] = []

    x_requested = spec.get("x_col")
    x_col = resolve_column(x_requested, available_cols) if x_requested else None
    if not x_col:
        resolution_warnings.append(f"Missing X column: '{x_requested}'")
        return None, resolution_warnings
    if x_requested and x_col != x_requested:
        resolution_warnings.append(f"Matched X column '{x_requested}' -> '{x_col}'")

    y_cols: list[str] = []
    for requested_col in spec.get("y_cols") or []:
        resolved = resolve_column(requested_col, available_cols)
        if resolved:
            y_cols.append(resolved)
            if resolved != requested_col:
                resolution_warnings.append(
                    f"Matched Y column '{requested_col}' -> '{resolved}'"
                )
        else:
            resolution_warnings.append(f"Missing Y column: '{requested_col}'")

    y2_cols: list[str] = []
    for requested_col in spec.get("y2_cols") or []:
        resolved = resolve_column(requested_col, available_cols)
        if resolved:
            y2_cols.append(resolved)
            if resolved != requested_col:
                resolution_warnings.append(
                    f"Matched Y2 column '{requested_col}' -> '{resolved}'"
                )
        else:
            resolution_warnings.append(f"Missing Y2 column: '{requested_col}'")

    if not y_cols and not y2_cols:
        resolution_warnings.append("No Y columns could be resolved.")
        return None, resolution_warnings

    resolved_spec = dict(spec)
    resolved_spec["x_col"] = x_col
    resolved_spec["y_cols"] = y_cols
    resolved_spec["y2_cols"] = y2_cols
    return make_figure(df, resolved_spec), resolution_warnings


def _sample_positions(length: int, max_points: int) -> list[int]:
    """Pick evenly spaced positions while keeping the first and last point."""
    if length <= max_points:
        return list(range(length))
    if max_points <= 1:
        return [0]

    last_position = length - 1
    return [
        int(round((offset * last_position) / (max_points - 1)))
        for offset in range(max_points)
    ]


def _downsample_series(series: pd.Series, max_points: int) -> pd.Series:
    """Reduce a series to a fixed point budget for compact previews."""
    if series.empty or len(series) <= max_points:
        return series
    return series.iloc[_sample_positions(len(series), max_points)]


def make_column_preview_figure(
    series: pd.Series,
    x_series: pd.Series | None = None,
    x_label: str | None = None,
    *,
    x_sorted: bool = False,
    max_points: int = COLUMN_PREVIEW_MAX_POINTS,
) -> go.Figure | None:
    """Create a compact preview chart for one column."""
    try:
        if pd.api.types.is_numeric_dtype(series):
            values = pd.to_numeric(series, errors="coerce")

            if x_series is not None:
                x_name = x_label or "x"
                x_values = (
                    x_series
                    if pd.api.types.is_datetime64_any_dtype(x_series)
                    else pd.to_datetime(x_series, errors="coerce")
                )
                if not isinstance(x_values, pd.Series):
                    x_values = pd.Series(
                        x_values,
                        index=values.index if len(x_values) == len(values) else None,
                    )
                common_index = x_values.index.intersection(values.index, sort=False)
                plot_x = x_values.loc[common_index]
                plot_values = values.loc[common_index]
                valid_mask = plot_x.notna() & plot_values.notna()
                plot_x = plot_x[valid_mask]
                plot_values = plot_values[valid_mask]

                if not plot_x.empty:
                    if not x_sorted:
                        plot_x = plot_x.sort_values(kind="stable")
                        plot_values = plot_values.loc[plot_x.index]
                    plot_x = _downsample_series(plot_x, max_points=max_points)
                    plot_values = plot_values.loc[plot_x.index]
                    plot_df = pd.DataFrame(
                        {x_name: plot_x.to_numpy(), "value": plot_values.to_numpy()}
                    )
                    fig = px.line(plot_df, x=x_name, y="value", template="plotly_white")
                else:
                    plot_values = values.dropna()
                    if plot_values.empty:
                        return None
                    plot_values = _downsample_series(
                        plot_values, max_points=max_points
                    )
                    plot_df = pd.DataFrame(
                        {"idx": plot_values.index, "value": plot_values.to_numpy()}
                    )
                    fig = px.line(plot_df, x="idx", y="value", template="plotly_white")
            else:
                plot_values = values.dropna()
                if plot_values.empty:
                    return None
                plot_values = _downsample_series(plot_values, max_points=max_points)
                plot_df = pd.DataFrame(
                    {"idx": plot_values.index, "value": plot_values.to_numpy()}
                )
                fig = px.line(plot_df, x="idx", y="value", template="plotly_white")
        elif pd.api.types.is_datetime64_any_dtype(series):
            dt = pd.to_datetime(series, errors="coerce").dropna()
            if dt.empty:
                return None
            counts = dt.dt.date.value_counts().sort_index()
            plot_df = counts.rename_axis("date").reset_index(name="count")
            fig = px.line(plot_df, x="date", y="count", template="plotly_white")
        else:
            text = series.astype("string").fillna("<NA>")
            counts = text.value_counts(dropna=False).head(15)
            if counts.empty:
                return None
            plot_df = counts.rename_axis("value").reset_index(name="count")
            fig = px.bar(plot_df, x="value", y="count", template="plotly_white")

        fig.update_layout(
            height=185, margin={"l": 8, "r": 8, "t": 8, "b": 8}, showlegend=False
        )
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        return fig
    except Exception:
        LOGGER.exception("Failed to build preview chart for column '%s'.", series.name)
        return None
