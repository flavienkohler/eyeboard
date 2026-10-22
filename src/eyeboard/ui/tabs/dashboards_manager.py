"""Dashboards manager tab renderer."""

import json

import streamlit as st

from eyeboard.dashboards.document import (
    parse_single_dashboard,
)
from eyeboard.dashboards.model import (
    Dashboard,
    PlotSpec,
    new_id,
)
from eyeboard.services.columns import normalize_colname
from eyeboard.services.dashboards import (
    remove_dashboard_plot,
    update_dashboard_plot,
)
from eyeboard.ui.context import MainDatasetContext, dataset_fingerprint
from eyeboard.ui.persistence import persist_dashboards_with_feedback
from eyeboard.ui.plot_form import render_plot_form, render_preview
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown


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

    prefix = f"edit_{selected_plot_id}_{dataset_fingerprint(dataset)}"
    choices = render_plot_form(
        dataset, initial=selected_plot, key_prefix=prefix, date_filter=False
    )
    st.markdown("##### Plot Preview")
    edited_spec = render_preview(choices, f"{prefix}_preview")

    if st.button("Save plot changes", width="stretch", disabled=edited_spec is None):
        edited_spec = edited_spec.model_copy(update={"id": selected_plot.id})
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


def _format_plot_option(plot: PlotSpec) -> str:
    """Build a compact label for a plot selector."""
    series_count = len(plot.y_cols) + len(plot.y2_cols)
    return f"{plot.title or 'Untitled'} ({series_count} series)"
