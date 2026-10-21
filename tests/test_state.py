import pytest
from helpers import make_dashboard

from eyeboard.dashboards.document import LoadResult
from eyeboard.state import (
    AppState,
    initialize_state,
    prune_recent_dashboard_ids,
    remember_recent_dashboard,
)


def _state_with(*dashboard_ids, recent=()):
    state = AppState({})
    state.dashboards = [make_dashboard(i, i) for i in dashboard_ids]
    state.recent_dashboard_ids = list(recent)
    return state


def test_keys_have_typed_defaults_created_on_first_use():
    store: dict = {}
    state = AppState(store)

    assert state.dashboards == [] and state.recent_dashboard_ids == []
    assert state.active_dashboard_id is None
    assert state.active_csv_source == "upload"
    assert state.read_date_mode == "Auto-detect" and state.read_date_format == ""
    assert isinstance(state.dashboards_loaded, LoadResult)
    assert "active_csv_source" in store  # the default is stored once read


def test_defaults_are_not_shared_between_states():
    first, second = AppState({}), AppState({})

    first.dashboards.append(make_dashboard())

    assert second.dashboards == []


def test_values_are_stored_under_the_attribute_name():
    store: dict = {}
    state = AppState(store)

    state.active_dashboard_id = "d1"

    assert store["active_dashboard_id"] == "d1"
    assert AppState(store).active_dashboard_id == "d1"


def test_a_mistyped_key_is_an_error_not_a_new_key():
    state = AppState({})

    with pytest.raises(AttributeError):
        state.active_dashboard_idd = "d1"
    with pytest.raises(AttributeError):
        _ = state.active_dashboard_idd


def test_remember_recent_dashboard_keeps_most_recent_first():
    state = _state_with(
        "dashboard-1",
        "dashboard-2",
        "dashboard-3",
        recent=["dashboard-2", "dashboard-1"],
    )

    remember_recent_dashboard(state, "dashboard-3")
    remember_recent_dashboard(state, "dashboard-1")

    assert state.recent_dashboard_ids == ["dashboard-1", "dashboard-3", "dashboard-2"]


def test_unknown_dashboards_are_not_remembered():
    state = _state_with("dashboard-1")

    remember_recent_dashboard(state, "other")
    remember_recent_dashboard(state, None)

    assert state.recent_dashboard_ids == []


def test_pruning_drops_deleted_dashboards():
    state = _state_with(
        "dashboard-1",
        "dashboard-3",
        recent=["dashboard-2", "dashboard-1", "dashboard-3"],
    )

    prune_recent_dashboard_ids(state)

    assert state.recent_dashboard_ids == ["dashboard-1", "dashboard-3"]


def test_initialize_state_loads_the_dashboards_only_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no dashboards file here: nothing to load
    state = AppState({})

    initialize_state(state)
    first_load = state.dashboards_loaded
    assert state.dashboards == []

    state.dashboards = [make_dashboard("changed")]
    initialize_state(state)

    assert state.dashboards_loaded is first_load
    assert [d.id for d in state.dashboards] == ["changed"]
