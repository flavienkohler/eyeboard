"""Compare tab: the loaded file (A) against a second file (B), plot by plot."""

from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from eyeboard.dashboards.model import Dashboard, PlotSpec
from eyeboard.plotting.export import png_config
from eyeboard.plotting.figures import render_plot_from_spec
from eyeboard.plotting.overlay import overlay_figures
from eyeboard.services.columns import resolve_column
from eyeboard.services.comparison import (
    Alignment,
    PlotComparison,
    compare_plot,
    overlap,
    shift_to_start,
)
from eyeboard.services.dataset import DataSource
from eyeboard.ui.cache import load_table_cached, parse_table_cached
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.exports import render_downloads
from eyeboard.ui.session import state
from eyeboard.ui.source_picker import render_source_picker
from eyeboard.ui.text import escape_markdown

OVERLAY = "Overlay"
SIDE_BY_SIDE = "Side by side"
TIMESTAMPS = "Timestamps"
ELAPSED = "Elapsed time"


@dataclass(slots=True)
class Side:
    """One of the two compared datasets, ready to draw."""

    label: str
    data: pd.DataFrame
    date_col: str | None


def render_compare_tab(dataset: MainDatasetContext) -> None:
    """Render the comparison of the loaded file with a second one."""
    st.caption(
        "A is the file loaded in the sidebar. Pick B here, then compare the plots of "
        "your saved dashboards on both."
    )
    source_b = render_source_picker("B", "compare_b")
    if source_b is None:
        st.info("Choose the file B to compare with.")
        return
    side_b = load_side_b(dataset, source_b)
    if side_b is None:
        return
    side_a = Side(dataset.label, dataset.df_parsed, dataset.date_col)

    st.caption(
        f"A: `{escape_markdown(side_a.label)}` ({len(side_a.data):,} rows)  |  "
        f"B: `{escape_markdown(side_b.label)}` ({len(side_b.data):,} rows). "
        "B is read with the same separator and decimal as A."
    )
    if dataset.date_col and side_b.date_col is None:
        st.warning(
            f"The date column '{dataset.date_col}' of A was not found in B, so the "
            "date range cannot be shared. Plots whose x is a date may not line up."
        )

    dashboards = pick_dashboards()
    if not dashboards:
        return
    mode, alignment = render_options()
    side_a, side_b = apply_shared_range(side_a, side_b, alignment)

    for dashboard in dashboards:
        render_dashboard_comparison(dashboard, side_a, side_b, mode, alignment)


def load_side_b(dataset: MainDatasetContext, source: DataSource) -> Side | None:
    """Read and date-parse the second file with the settings of the main one."""
    df, _, error = load_table_cached(source, dataset.read_options)
    if error:
        st.error(f"Could not read the file B: {error}")
        return None
    settings = dataset.date_settings
    column = (
        resolve_column(settings.column, list(df.columns)) if settings.column else None
    )
    parsed = parse_table_cached(
        source, dataset.read_options, replace(settings, column=column), df
    )
    return Side(source.label, parsed.df, column)


def pick_dashboards() -> list[Dashboard]:
    """Choose the saved dashboards to compare; empty when there is nothing to show."""
    if not state.dashboards:
        st.info("No saved dashboards yet. Create one in the **Plot** tab first.")
        return []
    ordered = sorted(state.dashboards, key=lambda d: d.name.lower())
    by_id = {d.id: d for d in ordered}
    active = state.active_dashboard_id
    chosen = st.multiselect(
        "Dashboards to compare",
        list(by_id),
        default=[active] if active in by_id else list(by_id)[:1],
        format_func=lambda value: by_id[value].name,
    )
    if not chosen:
        st.info("Select at least one dashboard to compare.")
    return [by_id[value] for value in chosen]


def render_options() -> tuple[str, Alignment]:
    """Choose how to show the files and how to line B up with A."""
    left, right = st.columns(2)
    mode = left.radio(
        "Show",
        [OVERLAY, SIDE_BY_SIDE],
        horizontal=True,
        key="compare_mode",
        help="Overlay draws B dashed over A. Side by side draws two charts.",
    )
    choice = right.radio(
        "Line B up with A by",
        [TIMESTAMPS, ELAPSED],
        horizontal=True,
        key="compare_alignment",
        help=(
            "Timestamps: the same moments. Elapsed time: each file counts from its "
            "own start, to compare two runs begun at different times."
        ),
    )
    return mode, "elapsed" if choice == ELAPSED else "timestamps"


def apply_shared_range(a: Side, b: Side, alignment: Alignment) -> tuple[Side, Side]:
    """Limit both files to the dates they share (timestamps alignment only)."""
    if alignment != "timestamps" or not a.date_col or not b.date_col:
        return a, b
    shared = overlap(a.data[a.date_col], b.data[b.date_col])
    if shared is None:
        if pd.api.types.is_datetime64_any_dtype(a.data[a.date_col]):
            st.warning("The two files do not cover any common period.")
        return a, b
    low, high = (value.to_pydatetime() for value in shared)
    with st.expander("Shared date range", expanded=False):
        start, end = st.slider(
            "Limit both files to",
            min_value=low,
            max_value=high,
            value=(low, high),
            key="compare_dates",
        )
    inside_a = a.data[a.data[a.date_col].between(start, end)]
    inside_b = b.data[b.data[b.date_col].between(start, end)]
    if inside_a.empty or inside_b.empty:
        st.warning("The shared date range leaves one of the files empty.")
    return replace(a, data=inside_a), replace(b, data=inside_b)


def render_dashboard_comparison(
    dashboard: Dashboard, a: Side, b: Side, mode: str, alignment: Alignment
) -> None:
    """Compare every plot of one dashboard."""
    with st.container(border=True):
        st.markdown(f"#### {escape_markdown(dashboard.name)}")
        for index, spec in enumerate(dashboard.plots, start=1):
            st.markdown(f"**{escape_markdown(spec.title or f'Plot {index}')}**")
            key = f"cmp_{dashboard.id}_{spec.id}"
            render_plot_comparison(spec, a, b, mode, alignment, key)


def line_up_b(spec: PlotSpec, a: Side, b: Side) -> pd.DataFrame:
    """B with its x column moved to start where A starts (elapsed-time overlays)."""
    x_a = resolve_column(spec.x_col, list(a.data.columns))
    x_b = resolve_column(spec.x_col, list(b.data.columns))
    if x_a is None or x_b is None:
        return b.data
    return b.data.assign(**{x_b: shift_to_start(b.data[x_b], a.data[x_a])})


def render_plot_comparison(
    spec: PlotSpec, a: Side, b: Side, mode: str, alignment: Alignment, key: str
) -> None:
    """Draw one plot on A and B, and measure the gap between them."""
    data_b = line_up_b(spec, a, b) if alignment == "elapsed" else b.data
    fig_a, warnings_a = render_plot_from_spec(a.data, spec, list(a.data.columns))
    fig_b, warnings_b = render_plot_from_spec(data_b, spec, list(data_b.columns))
    render_notes(warnings_a, warnings_b)

    overlay = None
    title = spec.title or "comparison"
    if mode == OVERLAY and fig_a is not None and fig_b is not None:
        overlay = overlay_figures(fig_a, fig_b)
        st.plotly_chart(overlay, width="stretch", key=key, config=png_config(title))
    else:
        left, right = st.columns(2, vertical_alignment="top")
        for column, fig, side, name in (
            (left, fig_a, a, "A"),
            (right, fig_b, b, "B"),
        ):
            with column:
                st.caption(f"{name} - {escape_markdown(side.label)}")
                if fig is None:
                    st.error(f"This plot could not be drawn for {name}.")
                else:
                    st.plotly_chart(
                        fig,
                        width="stretch",
                        key=f"{key}_{name}",
                        config=png_config(f"{title}_{name}"),
                    )

    result = compare_plot(spec, a.data, data_b, alignment=alignment)
    table = metrics_frame(result)
    render_metrics(table, result.notes)
    render_downloads(
        toggle_key=f"{key}_export",
        name=f"{title}_comparison",
        fig=overlay,
        table=table,
        table_label="Metrics (CSV)",
    )


def render_notes(warnings_a: list[str], warnings_b: list[str]) -> None:
    """List the column-matching notes of both files in one expander."""
    notes = [("A", w) for w in warnings_a] + [("B", w) for w in warnings_b]
    if not notes:
        return
    with st.expander(f"Notes ({len(notes)})", expanded=False):
        for name, warning in notes:
            text = f"{name}: {warning}"
            (st.info if warning.startswith("Matched ") else st.warning)(text)


def metrics_frame(result: PlotComparison) -> pd.DataFrame | None:
    """RMSE, MAE, bias and correlation per series as a table, if any were measured."""
    if not result.rows:
        return None
    return pd.DataFrame(
        {
            "series": [name for name, _ in result.rows],
            "points": [r.points for _, r in result.rows],
            "RMSE": [r.rmse for _, r in result.rows],
            "MAE": [r.mae for _, r in result.rows],
            "bias (B - A)": [r.bias for _, r in result.rows],
            "correlation": [r.correlation for _, r in result.rows],
        }
    )


def render_metrics(table: pd.DataFrame | None, notes: list[str]) -> None:
    """Show the metrics table, and what could not be compared."""
    if table is not None:
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={
                name: st.column_config.NumberColumn(format="%.4g")
                for name in ("RMSE", "MAE", "bias (B - A)", "correlation")
            },
        )
    for note in notes:
        st.caption(escape_markdown(note))
