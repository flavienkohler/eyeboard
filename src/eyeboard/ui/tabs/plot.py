"""Plot tab renderer: build one plot, see it, save it into a dashboard."""

import streamlit as st

from eyeboard.dashboards.model import PlotSpec, new_id
from eyeboard.services.dashboards import add_plot_to_dashboards
from eyeboard.state import remember_recent_dashboard
from eyeboard.ui.context import MainDatasetContext, dataset_fingerprint
from eyeboard.ui.persistence import persist_dashboards_with_feedback
from eyeboard.ui.plot_form import render_plot_form, render_preview
from eyeboard.ui.session import state

NEW_DASHBOARD = None  # the "Save into" choice that creates a dashboard


def render_plot_tab(dataset: MainDatasetContext) -> None:
    """Render the Plot tab: controls on the left, figure and saving on the right."""
    controls, result = st.columns([1, 2], gap="large")
    with controls:
        choices = render_plot_form(
            dataset,
            initial=None,
            key_prefix=f"plot_{dataset_fingerprint(dataset)}",
            date_filter=True,
        )
    with result:
        spec = render_preview(choices, "plot_preview")
        st.divider()
        render_save_section(spec)


def render_save_section(spec: PlotSpec | None) -> None:
    """Choose a dashboard (or a new one) and save the plot into it."""
    st.markdown("##### Save to dashboard")
    by_id = {d.id: d for d in sorted(state.dashboards, key=lambda d: d.name.lower())}
    options = [NEW_DASHBOARD, *by_id]
    # Right after a save the new dashboard is the natural target of the next one.
    index = (
        options.index(state.plot_save_target)
        if state.plot_save_target in options
        else 0
    )
    target = st.selectbox(
        "Save into",
        options,
        index=index,
        format_func=lambda value: (
            "New dashboard" if value is NEW_DASHBOARD else by_id[value].name
        ),
    )
    if target is NEW_DASHBOARD:
        name = st.text_input(
            "Dashboard name",
            placeholder="e.g. Discharge dashboard",
            help="A name that already exists adds the plot to that dashboard.",
        )
    else:
        name = by_id[target].name
    label = st.text_input("Plot label (optional)", placeholder="e.g. Q (m3/s) vs time")

    disabled = spec is None or not name.strip()
    if st.button("Save to dashboard", width="stretch", disabled=disabled):
        save_plot(spec, name.strip(), label.strip())


def save_plot(spec: PlotSpec | None, name: str, label: str) -> None:
    """Add the plot to the named dashboard and save the dashboards."""
    if spec is None:
        return
    plot = spec.model_copy(update={"id": new_id(), "title": label or spec.title})
    dashboards, target, created = add_plot_to_dashboards(state.dashboards, name, plot)
    if not persist_dashboards_with_feedback(dashboards):
        return
    state.active_dashboard_id = target.id
    state.plot_save_target = target.id
    remember_recent_dashboard(state, target.id)
    st.toast(
        f"Dashboard '{target.name}' created."
        if created
        else f"Plot added to '{target.name}'."
    )
    st.rerun()
