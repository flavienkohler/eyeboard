"""Typed access to the application state.

Streamlit keeps state in ``st.session_state``, a mapping of string keys. Spread
over many modules, a typo in a key silently creates a new one. ``AppState``
declares every key the application owns, with its type and default, so editors
can check it and a typo is an error.

It works over any mutable mapping, so it can be tested without Streamlit; the
interface uses ``eyeboard.ui.session.state``, which wraps ``st.session_state``.
"""

from collections.abc import Callable, MutableMapping
from typing import Any, Generic, TypeVar, overload

from eyeboard.dashboards.document import LoadResult
from eyeboard.dashboards.model import Dashboard
from eyeboard.services.dashboards import load_dashboards
from eyeboard.services.legacy import LegacyImport, import_legacy_files

RECENT_DASHBOARD_LIMIT = 8

T = TypeVar("T")


class StateKey(Generic[T]):
    """One typed entry of the application state, created with its default."""

    def __init__(self, default: Callable[[], T]) -> None:
        self._default = default
        self.name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    @overload
    def __get__(self, instance: None, owner: type) -> "StateKey[T]": ...
    @overload
    def __get__(self, instance: "AppState", owner: type) -> T: ...
    def __get__(self, instance: "AppState | None", owner: type) -> "T | StateKey[T]":
        if instance is None:
            return self
        store = instance.store
        if self.name not in store:
            store[self.name] = self._default()
        return store[self.name]

    def __set__(self, instance: "AppState", value: T) -> None:
        instance.store[self.name] = value


class AppState:
    """The state the application owns, as typed attributes over a mapping."""

    # Saved dashboards and what happened when they were loaded.
    dashboards = StateKey[list[Dashboard]](list)
    dashboards_loaded = StateKey[LoadResult](LoadResult)
    legacy_import = StateKey[LegacyImport](LegacyImport)
    active_dashboard_id = StateKey[str | None](lambda: None)
    recent_dashboard_ids = StateKey[list[str]](list)

    # Which CSV is active and how it got there.
    active_csv_source = StateKey[str](lambda: "upload")
    active_recent_csv_id = StateKey[str | None](lambda: None)
    last_uploaded_csv_signature = StateKey[str | None](lambda: None)
    remembered_upload_key = StateKey[str | None](lambda: None)

    # Date settings (also the keys of the sidebar widgets).
    date_settings_source = StateKey[str | None](lambda: None)
    read_date_col = StateKey[str | None](lambda: None)
    read_date_mode = StateKey[str](lambda: "Auto-detect")
    read_date_format = StateKey[str](str)

    # Explore tab (also the keys of its widgets).
    explore_signature = StateKey[str | None](lambda: None)
    explore_filter = StateKey[str](str)
    explore_show_rows = StateKey[bool](lambda: False)
    explore_mini_plots = StateKey[bool](lambda: False)
    explore_page_size = StateKey[int](lambda: 18)
    explore_page = StateKey[int](lambda: 1)

    # Small bits of per-tab memory.
    last_imported_json_signature = StateKey[str | None](lambda: None)
    plot_save_target = StateKey[str | None](lambda: None)
    editing_plot_id = StateKey[str | None](lambda: None)

    # Compare tab (also the keys of its widgets).
    compare_mode = StateKey[str](lambda: "Overlay")
    compare_alignment = StateKey[str](lambda: "Timestamps")

    # No instance attributes other than the store: a mistyped name is an error.
    __slots__ = ("store",)

    def __init__(self, store: MutableMapping[str, Any]) -> None:
        self.store = store


def initialize_state(state: AppState) -> None:
    """Import files of older versions and load the saved dashboards, once per session."""
    if "dashboards_loaded" in state.store:
        return
    state.legacy_import = import_legacy_files()
    loaded = load_dashboards()
    state.dashboards_loaded = loaded
    state.dashboards = loaded.dashboards
    prune_recent_dashboard_ids(state)


def remember_recent_dashboard(state: AppState, dashboard_id: str | None) -> None:
    """Track recently used dashboard ids in most-recent-first order."""
    if not dashboard_id:
        return

    available_ids = {dashboard.id for dashboard in state.dashboards}
    if dashboard_id not in available_ids:
        return

    recent_ids = [
        recent_id
        for recent_id in state.recent_dashboard_ids
        if recent_id != dashboard_id and recent_id in available_ids
    ]
    state.recent_dashboard_ids = [dashboard_id, *recent_ids][:RECENT_DASHBOARD_LIMIT]


def prune_recent_dashboard_ids(state: AppState) -> None:
    """Drop deleted dashboards from the recent-dashboards list."""
    available_ids = {dashboard.id for dashboard in state.dashboards}
    state.recent_dashboard_ids = [
        dashboard_id
        for dashboard_id in state.recent_dashboard_ids
        if dashboard_id in available_ids
    ][:RECENT_DASHBOARD_LIMIT]
