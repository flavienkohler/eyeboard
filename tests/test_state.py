from helpers import make_dashboard

from eyeboard.state import initialize_session_state, remember_recent_dashboard


def _dashboards(*ids):
    return [make_dashboard(dashboard_id, dashboard_id) for dashboard_id in ids]


def test_remember_recent_dashboard_keeps_most_recent_first():
    session_state = {
        "dashboards": _dashboards("dashboard-1", "dashboard-2", "dashboard-3"),
        "recent_dashboard_ids": ["dashboard-2", "dashboard-1"],
    }

    remember_recent_dashboard(session_state, "dashboard-3")
    remember_recent_dashboard(session_state, "dashboard-1")

    assert session_state["recent_dashboard_ids"] == [
        "dashboard-1",
        "dashboard-3",
        "dashboard-2",
    ]


def test_initialize_session_state_prunes_deleted_recent_dashboards():
    session_state = {
        "dashboards": _dashboards("dashboard-1", "dashboard-3"),
        "recent_dashboard_ids": ["dashboard-2", "dashboard-1", "dashboard-3"],
    }

    initialize_session_state(session_state)

    assert session_state["recent_dashboard_ids"] == ["dashboard-1", "dashboard-3"]
    assert session_state["dashboards_loaded"] is not None
