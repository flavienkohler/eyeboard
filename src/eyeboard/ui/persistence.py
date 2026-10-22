"""Saving the dashboards from the interface."""

import streamlit as st

from eyeboard.dashboards.model import Dashboard
from eyeboard.services.dashboards import save_dashboards
from eyeboard.state import prune_recent_dashboard_ids
from eyeboard.ui.session import state


def persist_dashboards_with_feedback(
    new_dashboards: list[Dashboard],
    *,
    success_message: str | None = None,
) -> bool:
    """Save the dashboards, update the session and report the outcome."""
    error = save_dashboards(new_dashboards, loaded=state.dashboards_loaded)
    if error:
        st.error(error)
        return False

    state.dashboards = new_dashboards
    prune_recent_dashboard_ids(state)
    if success_message:
        st.toast(success_message)  # survives the rerun that usually follows
    return True
