"""Dashboards manager tab renderer."""

import json

import streamlit as st
from pydantic import ValidationError

from eyeboard.config import PLOT_TYPES, THEMES
from eyeboard.dashboards.document import (
    describe_validation_error,
    parse_single_dashboard,
)
from eyeboard.dashboards.model import (
    AGGREGATIONS,
    DASH_STYLES,
    Dashboard,
    PlotSpec,
    SeriesStyle,
    new_id,
)
from eyeboard.plotting.figures import render_plot_from_spec
from eyeboard.plotting.specs import build_plot_spec_from_builder
from eyeboard.services.columns import normalize_colname
from eyeboard.services.dashboards import (
    remove_dashboard_plot,
    update_dashboard_plot,
)
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.persistence import persist_dashboards_with_feedback
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown

DEFAULT_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]


def _dashboard_json(dashboard: Dashboard) -> str:
    """Render a dashboard as the JSON shown in the editor and exported."""
    return json.dumps(dashboard.model_dump(mode="json"), ensure_ascii=False, indent=2)


def _show_problems(title: str, problems: list[str]) -> None:
    """Show a headline and one line per problem."""
    st.error(title)
    for problem in problems:
        st.warning(escape_markdown(problem))


def render_dashboards_manager_tab(dataset: MainDatasetContext) -> None:
    """Render dashboard management UI."""
    st.markdown("#### Dashboards Manager")
    st.caption(
        "Manage dashboards, edit or remove individual plots, export/import, and edit JSON."
    )

    dashboards: list[Dashboard] = state.dashboards
    if not dashboards:
        st.info("No dashboards saved yet.")
        return

    ordered = sorted(dashboards, key=lambda dashboard: dashboard.name.lower())
    dashboards_by_id = {dashboard.id: dashboard for dashboard in ordered}
    sel_id = st.selectbox(
        "Select dashboard",
        options=[dashboard.id for dashboard in ordered],
        format_func=lambda value: dashboards_by_id[value].name,
    )
    sel = dashboards_by_id[sel_id]

    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="top")
    with c1:
        new_name = st.text_input("Rename", value=sel.name)
        if st.button("Apply rename", width="stretch"):
            renamed_dashboard = sel.model_copy(
                update={"name": new_name.strip() or sel.name}
            )
            new_dashboards = [
                renamed_dashboard if dashboard.id == sel_id else dashboard
                for dashboard in dashboards
            ]
            persist_dashboards_with_feedback(new_dashboards, success_message="Renamed.")
    with c2:
        st.download_button(
            "Export selected (JSON)",
            data=_dashboard_json(sel).encode("utf-8"),
            file_name=f"{normalize_colname(sel.name).replace(' ', '_') or 'dashboard'}.json",
            mime="application/json",
            width="stretch",
        )
    with c3:
        if st.button("Delete selected", type="secondary", width="stretch"):
            new_dashboards = [
                dashboard for dashboard in dashboards if dashboard.id != sel_id
            ]
            if persist_dashboards_with_feedback(
                new_dashboards, success_message="Deleted."
            ):
                if state.active_dashboard_id == sel_id:
                    state.active_dashboard_id = None
                st.rerun()

    st.divider()
    render_dashboard_plot_editor(sel, dashboards, dataset)

    st.divider()
    render_json_editor(sel, dashboards)

    st.divider()
    render_import(dashboards)


def render_json_editor(sel: Dashboard, dashboards: list[Dashboard]) -> None:
    """Render the advanced JSON editor of the selected dashboard."""
    with st.expander("Edit dashboard JSON (advanced)", expanded=False):
        edited = st.text_area("Dashboard JSON", value=_dashboard_json(sel), height=380)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Validate JSON", width="stretch"):
                _, problems = _parse_editor_text(edited, sel.id)
                if problems:
                    _show_problems("This JSON is not a valid dashboard.", problems)
                else:
                    st.success("Valid dashboard JSON.")
        with col_b:
            if st.button("Save JSON to dashboard", width="stretch"):
                updated, problems = _parse_editor_text(edited, sel.id)
                if updated is None:
                    _show_problems("Could not save this JSON.", problems)
                elif updated.id != sel.id and any(
                    dashboard.id == updated.id for dashboard in dashboards
                ):
                    st.error("This id already belongs to another dashboard.")
                elif persist_dashboards_with_feedback(
                    [updated if d.id == sel.id else d for d in dashboards],
                    success_message="Dashboard updated.",
                ):
                    st.rerun()


def _parse_editor_text(
    text: str, default_id: str
) -> tuple[Dashboard | None, list[str]]:
    """Parse the editor text into a dashboard, or list what is wrong."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc}"]
    if isinstance(raw, dict):
        raw.setdefault("id", default_id)
    return parse_single_dashboard(raw)


def render_import(dashboards: list[Dashboard]) -> None:
    """Render the dashboard import control."""
    st.markdown("##### Import dashboard JSON")
    upl = st.file_uploader(
        "Import a dashboard (.json)", type=["json"], key="import_json"
    )
    if upl is None:
        return
    upload_signature = f"{upl.name}:{len(upl.getvalue())}"
    if upload_signature == state.last_imported_json_signature:
        return

    try:
        raw = json.loads(upl.getvalue().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        st.error(f"Import failed, the file is not valid JSON: {exc}")
        return
    imported, problems = parse_single_dashboard(raw)
    if imported is None:
        _show_problems("Imported dashboard could not be read correctly.", problems)
        return
    if any(dashboard.id == imported.id for dashboard in dashboards):
        # Importing a copy of an existing dashboard (for example an export of it).
        imported = imported.model_copy(update={"id": new_id()})
    if persist_dashboards_with_feedback(
        [*dashboards, imported], success_message="Imported dashboard."
    ):
        state.last_imported_json_signature = upload_signature
        st.rerun()


def render_dashboard_plot_editor(
    sel: Dashboard,
    dashboards: list[Dashboard],
    dataset: MainDatasetContext,
) -> None:
    """Render plot-level edit and removal controls for one dashboard."""
    plots = sel.plots
    st.markdown("##### Edit Plot In Dashboard")
    if not plots:
        st.info("This dashboard contains no editable plots.")
        return

    plot_by_id = {plot.id: plot for plot in plots}
    selected_plot_id = st.selectbox(
        "Select plot",
        options=list(plot_by_id),
        format_func=lambda value: _format_plot_option(plot_by_id[value]),
    )
    selected_plot = plot_by_id[selected_plot_id]

    top_left, top_right = st.columns([1.7, 1], vertical_alignment="bottom")
    with top_left:
        st.caption(f"Editing plot inside dashboard {escape_markdown(sel.name)}.")
    with top_right:
        remove_disabled = len(plots) <= 1
        if st.button(
            "Remove selected plot",
            type="secondary",
            width="stretch",
            disabled=remove_disabled,
        ):
            updated_dashboard = remove_dashboard_plot(sel, selected_plot_id)
            new_dashboards = [
                updated_dashboard if dashboard.id == sel.id else dashboard
                for dashboard in dashboards
            ]
            if persist_dashboards_with_feedback(
                new_dashboards,
                success_message="Plot removed from dashboard.",
            ):
                st.rerun()
        if remove_disabled:
            st.caption("A dashboard must keep at least one plot.")

    editable_df = dataset.df_parsed
    editable_cols = dataset.cols
    plot_form_key = f"dashboard_plot_editor_{selected_plot_id}"
    initial_y2_cols = [col for col in selected_plot.y2_cols if col in editable_cols]
    initial_y_cols = [col for col in selected_plot.y_cols if col in editable_cols]
    x_default = (
        selected_plot.x_col
        if selected_plot.x_col in editable_cols
        else (
            dataset.date_col if dataset.date_col in editable_cols else editable_cols[0]
        )
    )

    with st.expander("Plot settings", expanded=True):
        left, right = st.columns(2, vertical_alignment="top")
        with left:
            plot_label = st.text_input(
                "Plot label",
                value=selected_plot.title or "",
                key=f"{plot_form_key}_title",
            )
            x_col = st.selectbox(
                "X axis",
                options=editable_cols,
                index=editable_cols.index(x_default),
                key=f"{plot_form_key}_x",
            )
            y_cols = st.multiselect(
                "Y axis (primary)",
                options=editable_cols,
                default=initial_y_cols,
                key=f"{plot_form_key}_y",
            )
            enable_y2 = st.toggle(
                "Enable secondary Y axis",
                value=bool(initial_y2_cols),
                key=f"{plot_form_key}_enable_y2",
            )
            y2_cols = (
                st.multiselect(
                    "Y axis (secondary)",
                    options=[col for col in editable_cols if col not in y_cols],
                    default=[col for col in initial_y2_cols if col not in y_cols],
                    key=f"{plot_form_key}_y2",
                )
                if enable_y2
                else []
            )
            plot_type = st.selectbox(
                "Type",
                options=PLOT_TYPES,
                index=PLOT_TYPES.index(selected_plot.plot_type),
                key=f"{plot_form_key}_type",
            )
        with right:
            theme = st.selectbox(
                "Theme",
                options=THEMES,
                index=THEMES.index(selected_plot.theme),
                key=f"{plot_form_key}_theme",
            )
            yaxis_title_1 = st.text_input(
                "Y1 axis title",
                value=selected_plot.yaxis_title_1 or "",
                key=f"{plot_form_key}_y1_title",
            )
            yaxis_title_2 = st.text_input(
                "Y2 axis title",
                value=selected_plot.yaxis_title_2 or "",
                key=f"{plot_form_key}_y2_title",
                disabled=not enable_y2,
            )
            color_options = [None, *editable_cols]
            color_col = st.selectbox(
                "Color/group by (optional)",
                options=color_options,
                index=(
                    color_options.index(selected_plot.color_col)
                    if selected_plot.color_col in color_options
                    else 0
                ),
                key=f"{plot_form_key}_color",
            )
            agg_options = [None, *AGGREGATIONS]
            agg = st.selectbox(
                "Aggregate Y by X",
                options=agg_options,
                index=agg_options.index(selected_plot.agg),
                key=f"{plot_form_key}_agg",
            )

    style_map = render_plot_style_editor(
        selected_plot=selected_plot,
        y_cols=y_cols,
        y2_cols=y2_cols,
        key_prefix=plot_form_key,
    )
    try:
        edited_spec = build_plot_spec_from_builder(
            title=plot_label.strip() or None,
            x_col=x_col,
            y_cols=y_cols,
            plot_type=plot_type,
            theme=theme,
            enable_secondary_axis=enable_y2,
            y2_cols=y2_cols,
            yaxis_title_1=yaxis_title_1.strip() or None,
            yaxis_title_2=yaxis_title_2.strip() or None,
            color_col=color_col,
            agg=agg,
            series_style=style_map,
        ).model_copy(update={"id": selected_plot.id})
    except ValidationError as exc:
        _show_problems(
            "These settings do not make a valid plot.",
            describe_validation_error(exc),
        )
        return

    st.markdown("##### Plot Preview")
    preview_fig, preview_warnings = render_plot_from_spec(
        editable_df,
        edited_spec,
        list(editable_df.columns),
    )
    for warning in preview_warnings:
        if warning.startswith("Matched "):
            st.info(warning)
        else:
            st.warning(warning)
    if preview_fig is not None:
        st.plotly_chart(
            preview_fig,
            width="stretch",
            key=f"{plot_form_key}_preview",
        )
    else:
        st.error("Could not render the edited plot on the current dataset.")

    if st.button("Save plot changes", width="stretch"):
        updated_dashboard = update_dashboard_plot(sel, selected_plot_id, edited_spec)
        new_dashboards = [
            updated_dashboard if dashboard.id == sel.id else dashboard
            for dashboard in dashboards
        ]
        if persist_dashboards_with_feedback(
            new_dashboards,
            success_message="Plot updated in dashboard.",
        ):
            st.rerun()


def render_plot_style_editor(
    *,
    selected_plot: PlotSpec,
    y_cols: list[str],
    y2_cols: list[str],
    key_prefix: str,
) -> dict[str, dict[str, object]]:
    """Render per-series style controls in the manager tab."""
    with st.expander("Series styling", expanded=False):
        st.caption("Adjust line color, width, and dash style for each visible series.")
        style_map: dict[str, dict[str, object]] = {}
        series_list = list(dict.fromkeys((y_cols or []) + (y2_cols or [])))
        if not series_list:
            st.info("Select Y columns to edit series styles.")
            return style_map

        for idx, series_name in enumerate(series_list):
            default_style = selected_plot.series_style.get(series_name) or SeriesStyle()
            safe = normalize_colname(series_name).replace(" ", "_") or "series"
            st.markdown(f"**{escape_markdown(series_name)}**")
            c1, c2, c3 = st.columns([1.2, 1, 1], vertical_alignment="center")
            with c1:
                color = st.color_picker(
                    "Color",
                    value=default_style.color
                    or DEFAULT_COLORS[idx % len(DEFAULT_COLORS)],
                    key=f"{key_prefix}_{safe}_color",
                    label_visibility="collapsed",
                )
            with c2:
                width = st.slider(
                    "Width",
                    min_value=1,
                    max_value=8,
                    value=int(default_style.width or 2),
                    key=f"{key_prefix}_{safe}_width",
                    label_visibility="collapsed",
                )
            with c3:
                dash = st.selectbox(
                    "Style",
                    options=DASH_STYLES,
                    index=DASH_STYLES.index(default_style.dash or "solid"),
                    key=f"{key_prefix}_{safe}_dash",
                    label_visibility="collapsed",
                )
            style_map[series_name] = {
                "color": color,
                "width": width,
                "dash": dash,
            }
        return style_map


def _format_plot_option(plot: PlotSpec) -> str:
    """Build a compact label for a plot selector."""
    series_count = len(plot.y_cols) + len(plot.y2_cols)
    return f"{plot.title or 'Untitled'} ({series_count} series)"
