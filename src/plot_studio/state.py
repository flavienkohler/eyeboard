"""Session state helpers for the Streamlit app."""

from collections.abc import MutableMapping
from typing import Any

from plot_studio.services.templates import load_saved_configs_from_disk

RECENT_CONFIG_LIMIT = 8


def initialize_session_state(session_state: MutableMapping[str, Any]) -> None:
    """Ensure all required Streamlit session state keys exist."""
    if "saved_configs" not in session_state:
        saved_configs, load_error = load_saved_configs_from_disk()
        session_state["saved_configs"] = saved_configs
        session_state["saved_configs_load_error"] = load_error

    if "saved_configs_load_error" not in session_state:
        session_state["saved_configs_load_error"] = None

    if "df" not in session_state:
        session_state["df"] = None

    if "file_label" not in session_state:
        session_state["file_label"] = ""

    if "active_csv_source" not in session_state:
        session_state["active_csv_source"] = "upload"

    if "active_recent_csv_id" not in session_state:
        session_state["active_recent_csv_id"] = None

    if "last_uploaded_csv_signature" not in session_state:
        session_state["last_uploaded_csv_signature"] = None

    if "read_report" not in session_state:
        session_state["read_report"] = None

    if "active_dashboard_id" not in session_state:
        session_state["active_dashboard_id"] = None

    if "recent_config_ids" not in session_state:
        session_state["recent_config_ids"] = []

    if "read_date_col" not in session_state:
        session_state["read_date_col"] = None

    if "read_date_mode" not in session_state:
        session_state["read_date_mode"] = (
            "Day-first" if session_state.get("read_dayfirst") else "Auto-detect"
        )

    if "read_date_format" not in session_state:
        session_state["read_date_format"] = ""

    prune_recent_config_ids(session_state)


def remember_recent_config(
    session_state: MutableMapping[str, Any],
    config_id: str | None,
    *,
    max_items: int = RECENT_CONFIG_LIMIT,
) -> None:
    """Track recently used config ids in most-recent-first order."""
    if not config_id:
        return

    available_ids = {
        cfg.get("id") for cfg in session_state.get("saved_configs", []) if cfg.get("id")
    }
    if config_id not in available_ids:
        return

    recent_ids = [
        recent_id
        for recent_id in session_state.get("recent_config_ids", [])
        if recent_id != config_id and recent_id in available_ids
    ]
    session_state["recent_config_ids"] = [config_id, *recent_ids][:max_items]


def prune_recent_config_ids(session_state: MutableMapping[str, Any]) -> None:
    """Drop deleted configs from the recent-config list."""
    available_ids = {
        cfg.get("id") for cfg in session_state.get("saved_configs", []) if cfg.get("id")
    }
    session_state["recent_config_ids"] = [
        config_id
        for config_id in session_state.get("recent_config_ids", [])
        if config_id in available_ids
    ][:RECENT_CONFIG_LIMIT]
