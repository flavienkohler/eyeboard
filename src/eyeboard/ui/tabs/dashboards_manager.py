"""Managing saved dashboards: rename, export, delete, reorder, edit plots, import."""

import hashlib
import json

import streamlit as st

from eyeboard.dashboards.document import parse_single_dashboard
from eyeboard.dashboards.model import Dashboard, PlotSpec, new_id
from eyeboard.services.columns import normalize_colname
from eyeboard.services.dashboards import (
    move_dashboard_plot,
    name_is_taken,
    remove_dashboard_plot,
    unique_name,
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


def _replace(dashboards: list[Dashboard], updated: Dashboard) -> list[Dashboard]:
    """The list with one dashboard (matched by id) replaced."""
    return [updated if d.id == updated.id else d for d in dashboards]


def render_manager(dataset: MainDatasetContext) -> None:
    """Render the dashboard management controls."""
    dashboards: list[Dashboard] = state.dashboards
    if not dashboards:
        st.info("No dashboards saved yet. Save one from the Plot tab, or import one.")
        render_import(dashboards)
        return

    ordered = sorted(dashboards, key=lambda dashboard: dashboard.name.lower())
    by_id = {dashboard.id: dashboard for dashboard in ordered}
    ids = list(by_id)
    # The dashboard shown above is the one managed here: one selection, not two.
    index = (
        ids.index(state.active_dashboard_id) if state.active_dashboard_id in ids else 0
    )
    sel_id = st.selectbox(
        "Dashboard",
        ids,
        index=index,
        format_func=lambda value: by_id[value].name,
    )
    sel = by_id[sel_id]

    render_dashboard_actions(sel, dashboards)
    st.divider()
    render_plot_list(sel, dashboards, dataset)
    st.divider()
    render_json_editor(sel, dashboards)
    render_import(dashboards)


def render_dashboard_actions(sel: Dashboard, dashboards: list[Dashboard]) -> None:
    """Rename, export and delete the selected dashboard."""
    c1, c2, c3 = st.columns(3, vertical_alignment="bottom")
    with c1:
        new_name = st.text_input("Rename", value=sel.name).strip()
        if st.button("Apply rename", width="stretch", disabled=not new_name):
            if name_is_taken(dashboards, new_name, ignore_id=sel.id):
                st.error(f"A dashboard named '{new_name}' already exists.")
            else:
                renamed = sel.model_copy(update={"name": new_name})
                persist_dashboards_with_feedback(
                    _replace(dashboards, renamed), success_message="Renamed."
                )
    with c2:
        st.download_button(
            "Export (JSON)",
            data=_dashboard_json(sel).encode("utf-8"),
            file_name=f"{normalize_colname(sel.name).replace(' ', '_') or 'dashboard'}.json",
            mime="application/json",
            width="stretch",
        )
    with c3:
        with st.popover("Delete..."):
            st.write(f"Delete **{escape_markdown(sel.name)}** and its plots?")
            if st.button("Yes, delete", type="primary", key="confirm_delete_dashboard"):
                remaining = [d for d in dashboards if d.id != sel.id]
                if persist_dashboards_with_feedback(
                    remaining, success_message="Deleted."
                ):
                    state.active_dashboard_id = None
                    state.editing_plot_id = None
                    st.rerun()


def _plot_summary(plot: PlotSpec) -> str:
    """One line describing a plot in the list."""
    series = len(plot.y_cols) + len(plot.y2_cols)
    return f"**{escape_markdown(plot.title or 'Untitled')}**  \n{plot.plot_type}, {series} series"


def render_plot_list(
    sel: Dashboard, dashboards: list[Dashboard], dataset: MainDatasetContext
) -> None:
    """List the plots of the dashboard with move, edit and remove buttons."""
    st.markdown("##### Plots")
    last = len(sel.plots) - 1
    for position, plot in enumerate(sel.plots):
        info, up, down, edit, remove = st.columns(
            [4, 0.7, 0.7, 1, 1.3], vertical_alignment="center"
        )
        info.markdown(_plot_summary(plot))
        if up.button("Up", key=f"up_{plot.id}", disabled=position == 0):
            persist_dashboards_with_feedback(
                _replace(dashboards, move_dashboard_plot(sel, plot.id, -1))
            )
            st.rerun()
        if down.button("Down", key=f"down_{plot.id}", disabled=position == last):
            persist_dashboards_with_feedback(
                _replace(dashboards, move_dashboard_plot(sel, plot.id, +1))
            )
            st.rerun()
        if edit.button("Edit", key=f"edit_{plot.id}"):
            state.editing_plot_id = plot.id
            st.rerun()
        with remove.popover("Remove", disabled=len(sel.plots) <= 1):
            st.write("Remove this plot from the dashboard?")
            if st.button("Yes, remove", type="primary", key=f"confirm_rm_{plot.id}"):
                updated = remove_dashboard_plot(sel, plot.id)
                if persist_dashboards_with_feedback(_replace(dashboards, updated)):
                    if state.editing_plot_id == plot.id:
                        state.editing_plot_id = None
                    st.rerun()
    if len(sel.plots) <= 1:
        st.caption("A dashboard must keep at least one plot.")

    editing = next((p for p in sel.plots if p.id == state.editing_plot_id), None)
    if editing is not None:
        render_plot_editor(sel, editing, dashboards, dataset)


def render_plot_editor(
    sel: Dashboard,
    plot: PlotSpec,
    dashboards: list[Dashboard],
    dataset: MainDatasetContext,
) -> None:
    """Edit one plot with the same form as the Plot tab, started from the saved plot."""
    with st.container(border=True):
        st.markdown(f"##### Editing: {escape_markdown(plot.title or 'Untitled')}")
        prefix = f"edit_{plot.id}_{dataset_fingerprint(dataset)}"
        choices = render_plot_form(
            dataset, initial=plot, key_prefix=prefix, date_filter=False
        )
        edited = render_preview(choices, f"{prefix}_preview")

        save, close = st.columns(2)
        if save.button("Save plot changes", width="stretch", disabled=edited is None):
            edited = edited.model_copy(update={"id": plot.id})
            updated = update_dashboard_plot(sel, plot.id, edited)
            if persist_dashboards_with_feedback(
                _replace(dashboards, updated), success_message="Plot updated."
            ):
                st.rerun()
        if close.button("Close editor", width="stretch"):
            state.editing_plot_id = None
            st.rerun()


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
                    d.id == updated.id for d in dashboards
                ):
                    st.error("This id already belongs to another dashboard.")
                elif name_is_taken(dashboards, updated.name, ignore_id=sel.id):
                    st.error(f"A dashboard named '{updated.name}' already exists.")
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
    with st.expander("Import a dashboard (JSON)", expanded=False):
        upl = st.file_uploader(
            "Dashboard file (.json)", type=["json"], key="import_json"
        )
        if upl is None:
            return
        content = upl.getvalue()
        # By content, so two different files with the same name and size differ.
        signature = hashlib.sha256(content).hexdigest()
        if signature == state.last_imported_json_signature:
            return

        try:
            raw = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            st.error(f"Import failed, the file is not valid JSON: {exc}")
            return
        imported, problems = parse_single_dashboard(raw)
        if imported is None:
            _show_problems("Imported dashboard could not be read correctly.", problems)
            return
        updates: dict[str, str] = {"name": unique_name(dashboards, imported.name)}
        if any(d.id == imported.id for d in dashboards):
            # A copy of an existing dashboard (for example an export of it).
            updates["id"] = new_id()
        imported = imported.model_copy(update=updates)
        if persist_dashboards_with_feedback(
            [*dashboards, imported],
            success_message=f"Imported as '{imported.name}'.",
        ):
            state.last_imported_json_signature = signature
            st.rerun()
