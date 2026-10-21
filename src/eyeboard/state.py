"""Session state helpers for the Streamlit app."""

from collections.abc import MutableMapping
from typing import Any

from eyeboard.dashboards.document import LoadResult
from eyeboard.services.dashboards import load_dashboards

RECENT_DASHBOARD_LIMIT = 8


def initialize_session_state(session_state: MutableMapping[str, Any]) -> None:
    """Ensure all required Streamlit session state keys exist."""
    if "dashboards" not in session_state:
        loaded = load_dashboards()
        session_state["dashboards"] = loaded.dashboards
        session_state["dashboards_loaded"] = loaded

    if "dashboards_loaded" not in session_state:
        session_state["dashboards_loaded"] = LoadResult()

    if "active_csv_source" not in session_state:
        session_state["active_csv_source"] = "upload"

    if "active_recent_csv_id" not in session_state:
        session_state["active_recent_csv_id"] = None

    if "last_uploaded_csv_signature" not in session_state:
        session_state["last_uploaded_csv_signature"] = None

    if "remembered_upload_key" not in session_state:
        session_state["remembered_upload_key"] = None

    if "active_dashboard_id" not in session_state:
        session_state["active_dashboard_id"] = None

    if "recent_dashboard_ids" not in session_state:
        session_state["recent_dashboard_ids"] = []

    if "date_settings_source" not in session_state:
        session_state["date_settings_source"] = None

    if "read_date_col" not in session_state:
        session_state["read_date_col"] = None

    if "read_date_mode" not in session_state:
        session_state["read_date_mode"] = (
            "Day-first" if session_state.get("read_dayfirst") else "Auto-detect"
        )

    if "read_date_format" not in session_state:
        session_state["read_date_format"] = ""

    prune_recent_dashboard_ids(session_state)


def remember_recent_dashboard(
    session_state: MutableMapping[str, Any],
    dashboard_id: str | None,
    *,
    max_items: int = RECENT_DASHBOARD_LIMIT,
) -> None:
    """Track recently used dashboard ids in most-recent-first order."""
    if not dashboard_id:
        return

    available_ids = {dashboard.id for dashboard in session_state.get("dashboards", [])}
    if dashboard_id not in available_ids:
        return

    recent_ids = [
        recent_id
        for recent_id in session_state.get("recent_dashboard_ids", [])
        if recent_id != dashboard_id and recent_id in available_ids
    ]
    session_state["recent_dashboard_ids"] = [dashboard_id, *recent_ids][:max_items]


def prune_recent_dashboard_ids(session_state: MutableMapping[str, Any]) -> None:
    """Drop deleted dashboards from the recent-dashboards list."""
    available_ids = {dashboard.id for dashboard in session_state.get("dashboards", [])}
    session_state["recent_dashboard_ids"] = [
        dashboard_id
        for dashboard_id in session_state.get("recent_dashboard_ids", [])
        if dashboard_id in available_ids
    ][:RECENT_DASHBOARD_LIMIT]
