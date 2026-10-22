"""The dashboard view: saved dashboards drawn on the current dataset."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from eyeboard.dashboards.model import Dashboard
from eyeboard.i18n import t
from eyeboard.plotting.export import png_config
from eyeboard.plotting.figures import is_info_note, render_plot_from_spec
from eyeboard.services.dashboard_sync import (
    apply_visible_y_ranges,
    compute_dashboard_sync_x_range,
    prepare_dashboard_x_columns,
)
from eyeboard.state import remember_recent_dashboard
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.exports import render_downloads
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown


def render_dashboard_view(dataset: MainDatasetContext) -> None:
    """Render the selected dashboards on the current dataset."""

    dashboards = state.dashboards
    if not dashboards:
        st.info(
            t("No saved dashboards yet. Build one in the **Plot** tab and save it.")
        )
        return

    ordered = sorted(dashboards, key=lambda dashboard: dashboard.name.lower())
    dashboards_by_id = {dashboard.id: dashboard for dashboard in ordered}
    dashboard_options = [dashboard.id for dashboard in ordered]

    active_id = state.active_dashboard_id
    default_selected = (
        [active_id] if active_id in dashboard_options else dashboard_options[:1]
    )
    selected_dashboard_ids = st.multiselect(
        t("Dashboards to show"),
        options=dashboard_options,
        default=default_selected,
        format_func=lambda value: dashboards_by_id[value].name,
    )

    if selected_dashboard_ids:
        state.active_dashboard_id = selected_dashboard_ids[0]
        remember_recent_dashboard(state, selected_dashboard_ids[0])

    if not selected_dashboard_ids:
        st.info(t("Select at least one dashboard."))
        return

    dash_df, sync_x_axis, date_col_dash = render_dashboard_global_options(dataset)
    dash_filtered = render_dashboard_date_filter(dash_df, date_col_dash)
    if dash_filtered.empty:
        st.warning(t("The current dashboard filters leave no rows to render."))
    available_cols = list(dash_filtered.columns)
    dash_plot_df = prepare_dashboard_x_columns(
        dash_filtered,
        selected_dashboard_ids,
        dashboards_by_id,
        available_cols,
    )
    available_cols = list(dash_plot_df.columns)
    shared_sync_default_range = (
        compute_dashboard_sync_x_range(
            dash_plot_df,
            selected_dashboard_ids,
            dashboards_by_id,
            available_cols,
        )
        if sync_x_axis
        else None
    )

    for dashboard_id in selected_dashboard_ids:
        dashboard = dashboards_by_id.get(dashboard_id)
        if not dashboard:
            continue

        with st.container(border=True):
            title_col, created_col = st.columns([3, 1], vertical_alignment="bottom")
            title_col.subheader(escape_markdown(dashboard.name))
            created_col.caption(
                t("Created: {date}", date=escape_markdown(dashboard.created_at))
            )

            dashboard_default_sync_range = (
                compute_dashboard_sync_x_range(
                    dash_plot_df,
                    [dashboard_id],
                    dashboards_by_id,
                    available_cols,
                )
                if sync_x_axis
                else None
            )
            dashboard_sync_range = (
                dashboard_default_sync_range or shared_sync_default_range
            )
            if sync_x_axis:
                st.caption(
                    t(
                        "Zoom any subplot in this dashboard to propagate its x-range to the others."
                    )
                )

            combined_fig, warnings_by_plot = build_dashboard_figure(
                dashboard,
                dash_plot_df,
                available_cols,
                sync_x_axis=sync_x_axis,
                sync_x_range=dashboard_sync_range,
            )

            for plot_title, warnings in warnings_by_plot:
                if not warnings:
                    continue
                with st.expander(
                    t("Column resolution notes - {plot_title}", plot_title=plot_title),
                    expanded=False,
                ):
                    for warning in warnings:
                        if is_info_note(warning):
                            st.info(warning)
                        else:
                            st.warning(warning)
                    st.caption(
                        t(
                            "Tip: You can fix this by editing the dashboard under Manage dashboards."
                        )
                    )

            if combined_fig is None:
                st.error(t("Could not render this dashboard on the current dataset."))
            else:
                st.plotly_chart(
                    combined_fig,
                    width="stretch",
                    key=f"dash_plot_{dashboard_id}",
                    config=png_config(dashboard.name),
                )
                render_downloads(
                    toggle_key=f"dash_export_{dashboard_id}",
                    name=dashboard.name,
                    fig=combined_fig,
                )


def render_dashboard_global_options(
    dataset: MainDatasetContext,
) -> tuple[pd.DataFrame, bool, str | None]:
    """Render the dashboard options; dates come from the shared date settings."""
    st.divider()
    sync_x_axis = st.toggle(
        t("Sync x-axis across dashboard plots"),
        value=True,
        key="dash_sync_x_axis",
        help=t(
            "When enabled, dashboard charts share the same x-axis range when possible."
        ),
    )
    return dataset.df_parsed, sync_x_axis, dataset.date_col


def render_dashboard_date_filter(
    dash_df: pd.DataFrame,
    date_col_dash: str | None,
) -> pd.DataFrame:
    """Render the dashboard date range filter below global options."""
    dash_filtered = dash_df

    if date_col_dash and date_col_dash in dash_df.columns:
        dt = dash_df[date_col_dash]
        if pd.api.types.is_datetime64_any_dtype(dt):
            valid_dt = dt.dropna()
            if not valid_dt.empty:
                min_d, max_d = valid_dt.min(), valid_dt.max()
                st.markdown(t("##### Dashboard date range"))
                date_range = st.slider(
                    t("Filter date range"),
                    min_value=min_d.to_pydatetime(),
                    max_value=max_d.to_pydatetime(),
                    value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                    key="dash_dateslider",
                )
                dash_filtered = dash_df[
                    (dash_df[date_col_dash] >= date_range[0])
                    & (dash_df[date_col_dash] <= date_range[1])
                ]
                if dash_filtered.empty:
                    st.warning(t("This date range leaves the dashboard with no rows."))

    return dash_filtered


def build_dashboard_figure(
    dashboard: Dashboard,
    dash_plot_df: pd.DataFrame,
    available_cols: list[str],
    *,
    sync_x_axis: bool,
    sync_x_range: tuple[object, object] | None,
) -> tuple[go.Figure | None, list[tuple[str, list[str]]]]:
    """Build a native Plotly subplot figure for one saved dashboard."""
    plots = dashboard.plots
    if not plots:
        return None, []

    subplot_titles = [
        plot.title or t("Plot {index}", index=idx)
        for idx, plot in enumerate(plots, start=1)
    ]
    specs = [[{"secondary_y": bool(plot.y2_cols)}] for plot in plots]
    combined_fig = make_subplots(
        rows=len(plots),
        cols=1,
        shared_xaxes=sync_x_axis,
        vertical_spacing=0.08,
        subplot_titles=subplot_titles,
        specs=specs,
    )
    combined_fig.update_layout(
        height=max(420, 320 * len(plots)),
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        hovermode="x unified" if sync_x_axis else "closest",
    )

    warnings_by_plot: list[tuple[str, list[str]]] = []
    seen_legend_names: set[str] = set()

    for idx, spec in enumerate(plots, start=1):
        plot_title = spec.title or t("Plot {index}", index=idx)
        child_fig, warnings = render_plot_from_spec(dash_plot_df, spec, available_cols)
        warnings_by_plot.append((plot_title, warnings))
        if child_fig is None:
            continue

        apply_synced_x_axis(child_fig, sync_x_range)
        apply_visible_y_ranges(
            child_fig,
            dash_plot_df,
            spec,
            available_cols,
            sync_x_range,
        )

        for trace in child_fig.data:
            trace_name = getattr(trace, "name", None)
            trace.showlegend = bool(trace_name) and trace_name not in seen_legend_names
            if trace_name:
                seen_legend_names.add(trace_name)
            combined_fig.add_trace(
                trace,
                row=idx,
                col=1,
                secondary_y=(getattr(trace, "yaxis", "y") == "y2"),
            )

        y1_title = (
            child_fig.layout.yaxis.title.text
            if child_fig.layout.yaxis and child_fig.layout.yaxis.title
            else None
        )
        if y1_title:
            combined_fig.update_yaxes(
                title_text=y1_title,
                row=idx,
                col=1,
                secondary_y=False,
            )

        y1_range = child_fig.layout.yaxis.range if child_fig.layout.yaxis else None
        if y1_range:
            combined_fig.update_yaxes(
                range=list(y1_range),
                row=idx,
                col=1,
                secondary_y=False,
            )

        child_yaxis2 = getattr(child_fig.layout, "yaxis2", None)
        y2_title = (
            child_yaxis2.title.text
            if child_yaxis2 is not None and child_yaxis2.title
            else None
        )
        if y2_title:
            combined_fig.update_yaxes(
                title_text=y2_title,
                row=idx,
                col=1,
                secondary_y=True,
            )

        y2_range = child_yaxis2.range if child_yaxis2 is not None else None
        if y2_range:
            combined_fig.update_yaxes(
                range=list(y2_range),
                row=idx,
                col=1,
                secondary_y=True,
            )

    apply_synced_x_axis(combined_fig, sync_x_range)
    return combined_fig, warnings_by_plot


def apply_synced_x_axis(
    fig,
    sync_x_range: tuple[object, object] | None,
) -> None:
    """Apply a shared x-axis range to a dashboard figure when possible."""
    if sync_x_range is None:
        return
    fig.update_xaxes(range=[sync_x_range[0], sync_x_range[1]])
