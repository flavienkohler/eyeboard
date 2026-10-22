"""Dashboards tab: the dashboards on top, their management in an expander below."""

import streamlit as st

from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.tabs.dashboard import render_dashboard_view
from eyeboard.ui.tabs.dashboards_manager import render_manager


def render_dashboards_tab(dataset: MainDatasetContext) -> None:
    """Render the saved dashboards, then the tools to manage them."""
    render_dashboard_view(dataset)
    st.divider()
    with st.expander("Manage dashboards", expanded=False):
        render_manager(dataset)
