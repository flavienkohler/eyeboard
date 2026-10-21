"""Figure creation and rendering helpers."""

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from eyeboard.dashboards.model import PlotSpec
from eyeboard.plotting.builder import make_figure
from eyeboard.plotting.frame import prepare_plot_frame
from eyeboard.services.columns import resolve_column

LOGGER = logging.getLogger(__name__)
COLUMN_PREVIEW_MAX_POINTS = 300


def render_plot_from_spec(
    df: pd.DataFrame,
    spec: PlotSpec,
    available_cols: list[str],
) -> tuple[go.Figure | None, list[str]]:
    """Resolve columns and render a figure for the current dataframe."""
    resolution_warnings: list[str] = []

    x_requested = spec.x_col
    x_col = resolve_column(x_requested, available_cols) if x_requested else None
    if not x_col:
        resolution_warnings.append(f"Missing X column: '{x_requested}'")
        return None, resolution_warnings
    if x_requested and x_col != x_requested:
        resolution_warnings.append(f"Matched X column '{x_requested}' -> '{x_col}'")

    y_cols: list[str] = []
    for requested_col in spec.y_cols:
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
    for requested_col in spec.y2_cols:
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

    color_requested = spec.color_col
    color_col = (
        resolve_column(color_requested, available_cols) if color_requested else None
    )
    if color_requested and not color_col:
        resolution_warnings.append(f"Missing color column: '{color_requested}'")

    # model_copy skips validation on purpose: these are the dataset's column names.
    resolved_spec = spec.model_copy(
        update={
            "x_col": x_col,
            "y_cols": y_cols,
            "y2_cols": y2_cols,
            "color_col": color_col,
        }
    )

    plot_df, resolved_spec, frame_warnings = prepare_plot_frame(df, resolved_spec)
    resolution_warnings.extend(frame_warnings)
    if not resolved_spec.y_cols and not resolved_spec.y2_cols:
        return None, resolution_warnings
    return make_figure(plot_df, resolved_spec), resolution_warnings


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
                    plot_values = _downsample_series(plot_values, max_points=max_points)
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
