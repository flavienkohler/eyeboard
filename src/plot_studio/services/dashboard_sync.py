"""Helpers for synchronizing dashboard plot ranges."""

import pandas as pd
from pandas.api.types import is_object_dtype

from plot_studio.services.columns import resolve_column
from plot_studio.services.date_parsing import parse_date_series

DATETIME_PARSE_SUCCESS_THRESHOLD = 0.9


def prepare_dashboard_x_columns(
    dash_filtered: pd.DataFrame,
    selected_cfg_ids: list[str],
    id_to_cfg: dict[str, dict],
    available_cols: list[str],
) -> pd.DataFrame:
    """Coerce selected dashboard x-columns to datetimes when the signal is strong."""
    prepared_df = dash_filtered.copy()

    for cfg_id in selected_cfg_ids:
        cfg = id_to_cfg.get(cfg_id)
        if not cfg:
            continue
        plots = cfg.get("plots") or []
        for plot in plots:
            if not isinstance(plot, dict):
                continue

            x_requested = plot.get("x_col")
            if not isinstance(x_requested, str):
                continue
            matched_x = resolve_column(x_requested, available_cols)
            if matched_x is None or matched_x not in prepared_df.columns:
                continue

            series = prepared_df[matched_x]
            if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_numeric_dtype(
                series
            ):
                continue
            if not is_object_dtype(series):
                continue

            parsed = parse_date_series(series)
            non_null_count = int(series.notna().sum())
            if non_null_count == 0:
                continue
            success_ratio = float(parsed.notna().sum()) / float(non_null_count)
            if success_ratio >= DATETIME_PARSE_SUCCESS_THRESHOLD:
                prepared_df[matched_x] = parsed

    return prepared_df


def compute_dashboard_sync_x_range(
    dash_filtered: pd.DataFrame,
    selected_cfg_ids: list[str],
    id_to_cfg: dict[str, dict],
    available_cols: list[str],
) -> tuple[object, object] | None:
    """Compute a shared x-axis range for dashboard plots when possible."""
    min_x: object | None = None
    max_x: object | None = None
    detected_kind: str | None = None

    for cfg_id in selected_cfg_ids:
        cfg = id_to_cfg.get(cfg_id)
        if not cfg:
            continue
        plots = cfg.get("plots") or []
        for plot in plots:
            if not isinstance(plot, dict):
                continue

            x_requested = plot.get("x_col")
            if not isinstance(x_requested, str):
                continue
            matched_x = resolve_column(x_requested, available_cols)
            if matched_x is None:
                continue

            x_series = dash_filtered[matched_x].dropna()
            if x_series.empty:
                continue

            if pd.api.types.is_datetime64_any_dtype(x_series):
                current_kind = "datetime"
            elif pd.api.types.is_numeric_dtype(x_series):
                current_kind = "numeric"
            else:
                continue

            if detected_kind is None:
                detected_kind = current_kind
            elif detected_kind != current_kind:
                return None

            current_min = x_series.min()
            current_max = x_series.max()
            min_x = current_min if min_x is None else min(min_x, current_min)
            max_x = current_max if max_x is None else max(max_x, current_max)

    if min_x is None or max_x is None:
        return None
    return min_x, max_x


def coerce_component_sync_range(
    component_range: object,
    reference_range: tuple[object, object] | None,
) -> tuple[object, object] | None:
    """Convert a component-returned x-range into the app's internal range shape."""
    if reference_range is None or not isinstance(component_range, (list, tuple)):
        return None
    if len(component_range) != 2:
        return None

    ref_min, ref_max = reference_range
    raw_min, raw_max = component_range

    if isinstance(ref_min, pd.Timestamp) and isinstance(ref_max, pd.Timestamp):
        parsed_min = pd.to_datetime(raw_min, errors="coerce")
        parsed_max = pd.to_datetime(raw_max, errors="coerce")
        if pd.isna(parsed_min) or pd.isna(parsed_max):
            return None
        return parsed_min, parsed_max

    if isinstance(ref_min, (int, float)) and isinstance(ref_max, (int, float)):
        try:
            return float(raw_min), float(raw_max)
        except (TypeError, ValueError):
            return None

    return None


def sync_ranges_match(
    left: tuple[object, object] | None,
    right: tuple[object, object] | None,
) -> bool:
    """Compare two sync ranges while tolerating datetime payload variations."""
    if left is None or right is None:
        return left is right

    left_min, left_max = left
    right_min, right_max = right

    if isinstance(left_min, pd.Timestamp) and isinstance(right_min, pd.Timestamp):
        return left_min == right_min and left_max == right_max

    return left == right


def apply_visible_y_ranges(
    fig,
    df: pd.DataFrame,
    spec: dict,
    available_cols: list[str],
    sync_x_range: tuple[object, object] | None,
) -> None:
    """Auto-fit Y axes to the data visible inside the current synced X window."""
    if sync_x_range is None:
        return

    x_requested = spec.get("x_col")
    x_col = resolve_column(x_requested, available_cols) if x_requested else None
    if x_col is None or x_col not in df.columns:
        return

    visible_df = _filter_df_to_x_range(df, x_col, sync_x_range)
    if visible_df.empty:
        return

    y1_cols = _resolve_series_columns(spec.get("y_cols") or [], available_cols)
    y2_cols = _resolve_series_columns(spec.get("y2_cols") or [], available_cols)

    y1_range = _compute_axis_range(visible_df, y1_cols)
    y2_range = _compute_axis_range(visible_df, y2_cols)

    if y1_range is not None:
        fig.update_yaxes(range=[y1_range[0], y1_range[1]])
    if y2_range is not None:
        fig.update_layout(
            yaxis2={
                **(fig.layout.yaxis2.to_plotly_json() if fig.layout.yaxis2 else {}),
                "range": [y2_range[0], y2_range[1]],
            }
        )


def _resolve_series_columns(
    requested_cols: list[str],
    available_cols: list[str],
) -> list[str]:
    """Resolve requested series columns against the current dataframe columns."""
    resolved_cols: list[str] = []
    for requested_col in requested_cols:
        resolved = resolve_column(requested_col, available_cols)
        if resolved is not None:
            resolved_cols.append(resolved)
    return resolved_cols


def _filter_df_to_x_range(
    df: pd.DataFrame,
    x_col: str,
    sync_x_range: tuple[object, object],
) -> pd.DataFrame:
    """Restrict a dataframe to the current synced X window."""
    min_x, max_x = sync_x_range
    x_series = df[x_col]

    try:
        mask = (x_series >= min_x) & (x_series <= max_x)
    except TypeError:
        return df
    return df[mask]


def _compute_axis_range(
    df: pd.DataFrame,
    columns: list[str],
) -> tuple[float, float] | None:
    """Compute a padded numeric Y range across one axis worth of series."""
    min_y: float | None = None
    max_y: float | None = None

    for col in columns:
        if col not in df.columns:
            continue
        numeric_series = pd.to_numeric(df[col], errors="coerce").dropna()
        if numeric_series.empty:
            continue

        current_min = float(numeric_series.min())
        current_max = float(numeric_series.max())
        min_y = current_min if min_y is None else min(min_y, current_min)
        max_y = current_max if max_y is None else max(max_y, current_max)

    if min_y is None or max_y is None:
        return None

    if min_y == max_y:
        padding = max(abs(min_y) * 0.05, 1.0)
        return min_y - padding, max_y + padding

    padding = (max_y - min_y) * 0.05
    return min_y - padding, max_y + padding
