"""Dashboard tab renderer."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from plot_studio.config import DATE_PARSE_MODES
from plot_studio.plotting.figures import render_plot_from_spec
from plot_studio.state import remember_recent_config
from plot_studio.services.date_parsing import parse_dates_flexible
from plot_studio.services.dashboard_sync import (
    apply_visible_y_ranges,
    compute_dashboard_sync_x_range,
    prepare_dashboard_x_columns,
)
from plot_studio.services.templates import validate_saved_config
from plot_studio.ui.context import MainDatasetContext


def render_dashboard_tab(dataset: MainDatasetContext) -> None:
    """Render the dashboard tab."""
    st.markdown("#### Dashboard")
    st.caption(
        "Select one or more saved dashboards. Each dashboard renders its saved plots on the current dataset."
    )

    configs = st.session_state["saved_configs"]
    if not configs:
        st.info("No saved dashboards yet. Build one in **Plot Builder** and save it.")
        return

    ordered = sorted(configs, key=lambda cfg: (cfg.get("name") or "").lower())
    id_to_cfg = {cfg.get("id"): cfg for cfg in ordered}
    cfg_options = [cfg.get("id") for cfg in ordered]

    active_id = st.session_state.get("active_dashboard_id")
    default_selected = [active_id] if active_id in cfg_options else cfg_options[:1]
    selected_cfg_ids = st.multiselect(
        "Dashboards to display",
        options=cfg_options,
        default=default_selected,
        format_func=lambda value: id_to_cfg.get(value, {}).get("name", "Unnamed"),
    )

    if selected_cfg_ids:
        st.session_state["active_dashboard_id"] = selected_cfg_ids[0]
        remember_recent_config(st.session_state, selected_cfg_ids[0])

    if not selected_cfg_ids:
        st.info("Select at least one dashboard.")
        return

    dash_df, sync_x_axis, date_col_dash = render_dashboard_global_options(dataset)
    dash_filtered = render_dashboard_date_filter(dash_df, date_col_dash)
    if dash_filtered.empty:
        st.warning("The current dashboard filters leave no rows to render.")
    available_cols = list(dash_filtered.columns)
    dash_plot_df = prepare_dashboard_x_columns(
        dash_filtered,
        selected_cfg_ids,
        id_to_cfg,
        available_cols,
    )
    available_cols = list(dash_plot_df.columns)
    shared_sync_default_range = (
        compute_dashboard_sync_x_range(
            dash_plot_df,
            selected_cfg_ids,
            id_to_cfg,
            available_cols,
        )
        if sync_x_axis
        else None
    )

    for cfg_id in selected_cfg_ids:
        cfg = id_to_cfg.get(cfg_id)
        if not cfg:
            continue

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                  <div style="font-size:18px; font-weight:700;">{cfg.get("name", "Unnamed")}</div>
                  <div style="opacity:0.8; font-size:12px;">Created: {cfg.get("created_at", "")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            config_errors = validate_saved_config(cfg)
            if config_errors:
                st.error("This dashboard could not be read correctly.")
                for error in config_errors:
                    st.warning(error)
                continue

            plots = cfg.get("plots") or []
            dashboard_default_sync_range = (
                compute_dashboard_sync_x_range(
                    dash_plot_df,
                    [cfg_id],
                    id_to_cfg,
                    available_cols,
                )
                if sync_x_axis
                else None
            )
            dashboard_sync_state_key = f"dash_zoom_sync_range_{cfg_id}"
            dashboard_sync_range = (
                st.session_state.get(dashboard_sync_state_key)
                or dashboard_default_sync_range
                or shared_sync_default_range
            )
            if sync_x_axis:
                st.caption(
                    "Zoom any subplot in this dashboard to propagate its x-range to the others."
                )

            combined_fig, warnings_by_plot = build_dashboard_figure(
                cfg,
                dash_plot_df,
                available_cols,
                sync_x_axis=sync_x_axis,
                sync_x_range=dashboard_sync_range,
            )

            for plot_title, warnings in warnings_by_plot:
                if not warnings:
                    continue
                with st.expander(
                    f"Column resolution notes - {plot_title}",
                    expanded=False,
                ):
                    for warning in warnings:
                        if warning.startswith("Matched "):
                            st.info(warning)
                        else:
                            st.warning(warning)
                    st.caption(
                        "Tip: You can fix this by editing the dashboard JSON in Dashboards Manager."
                    )

            if combined_fig is None:
                st.error("Could not render this dashboard on the current dataset.")
            else:
                st.plotly_chart(
                    combined_fig,
                    width="stretch",
                    key=f"dash_plot_{cfg_id}",
                )


def render_dashboard_global_options(
    dataset: MainDatasetContext,
) -> tuple[pd.DataFrame, bool, str | None]:
    """Render optional global date parsing and filtering for the dashboard."""
    st.divider()
    with st.expander("Global dashboard options", expanded=False):
        sync_x_axis = st.toggle(
            "Sync x-axis across dashboard plots",
            value=True,
            key="dash_sync_x_axis",
            help="When enabled, dashboard charts share the same x-axis range when possible.",
        )
        date_col_dash = st.selectbox(
            "Date/time column for dashboard (optional)",
            options=[None] + dataset.cols,
            index=(
                0
                if dataset.date_guess is None
                else ([None] + dataset.cols).index(dataset.date_guess)
            ),
        )
        dash_date_mode_default = st.session_state.get(
            "dash_date_mode",
            st.session_state.get("read_date_mode", "Auto-detect"),
        )
        if dash_date_mode_default not in DATE_PARSE_MODES:
            dash_date_mode_default = "Auto-detect"
        dash_date_mode = st.selectbox(
            "Date order",
            options=DATE_PARSE_MODES,
            index=DATE_PARSE_MODES.index(dash_date_mode_default),
            key="dash_date_mode",
            help="Auto-detect infers day/month order from the selected column when possible.",
        )
        date_format_dash = st.text_input(
            "Date format override (optional)",
            value="",
            key="dash_dateformat",
            help="Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection.",
        )
        dash_df = parse_dates_flexible(
            dataset.df,
            date_col_dash,
            date_mode=dash_date_mode,
            date_format=(date_format_dash or None),
        )
    return dash_df, sync_x_axis, date_col_dash


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
                st.markdown("##### Dashboard date range")
                date_range = st.slider(
                    "Filter date range",
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
                    st.warning("This date range leaves the dashboard with no rows.")

    st.session_state["dash_df_filtered"] = dash_filtered
    return st.session_state.get("dash_df_filtered", dash_df)


def build_dashboard_figure(
    cfg: dict,
    dash_plot_df: pd.DataFrame,
    available_cols: list[str],
    *,
    sync_x_axis: bool,
    sync_x_range: tuple[object, object] | None,
) -> tuple[go.Figure | None, list[tuple[str, list[str]]]]:
    """Build a native Plotly subplot figure for one saved dashboard."""
    plots = [plot for plot in (cfg.get("plots") or []) if isinstance(plot, dict)]
    if not plots:
        return None, []

    subplot_titles = [
        plot.get("title") or f"Plot {idx}" for idx, plot in enumerate(plots, start=1)
    ]
    specs = [[{"secondary_y": bool(plot.get("y2_cols"))}] for plot in plots]
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
        plot_title = spec.get("title") or f"Plot {idx}"
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
