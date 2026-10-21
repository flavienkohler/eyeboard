import json
import shutil
import uuid
from pathlib import Path

from plot_studio.services.dashboards import (
    find_dashboard_by_name,
    load_dashboards,
    remove_dashboard_plot,
    save_dashboards,
    update_dashboard_plot,
    validate_dashboard,
)


def make_workspace_temp_dir() -> Path:
    temp_dir = Path("tests") / "_tmp" / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_dashboard_persistence_round_trip():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        dashboards = [{"id": "dashboard-1", "name": "Main dashboard", "plots": []}]

        save_error = save_dashboards(dashboards, config_path)
        assert save_error is None

        loaded, load_error = load_dashboards(config_path)
        assert load_error is None
        assert loaded == dashboards
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_load_dashboards_filters_non_dict_items():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        config_path.write_text(
            json.dumps([{"id": "dashboard-1"}, "bad-entry", 42]),
            encoding="utf-8",
        )

        loaded, load_error = load_dashboards(config_path)
        assert load_error is None
        assert loaded == [{"id": "dashboard-1"}]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_load_dashboards_reports_invalid_json():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        config_path.write_text("{not-valid-json", encoding="utf-8")

        loaded, load_error = load_dashboards(config_path)

        assert loaded == []
        assert load_error is not None
        assert "Could not read saved dashboards" in load_error
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_validate_dashboard_reports_missing_plot_series():
    dashboard = {
        "id": "dashboard-1",
        "name": "Broken dashboard",
        "plots": [{"x_col": "time", "y_cols": [], "y2_cols": []}],
    }

    errors = validate_dashboard(dashboard)

    assert "Plot 1 must define at least one Y series." in errors


def test_validate_dashboard_accepts_minimal_valid_dashboard():
    dashboard = {
        "id": "dashboard-1",
        "name": "Valid dashboard",
        "plots": [{"x_col": "time", "y_cols": ["value"], "y2_cols": []}],
    }

    errors = validate_dashboard(dashboard)

    assert errors == []


def test_find_dashboard_by_name_matches_case_insensitively():
    dashboards = [
        {"id": "dashboard-1", "name": "Sensor Board", "plots": []},
        {"id": "dashboard-2", "name": "Meteo", "plots": []},
    ]

    match = find_dashboard_by_name(dashboards, "  sensor board  ")

    assert match is not None
    assert match["id"] == "dashboard-1"


def test_update_dashboard_plot_replaces_matching_plot_only():
    dashboard = {
        "id": "dash-1",
        "name": "Main",
        "plots": [
            {"id": "plot-1", "title": "A"},
            {"id": "plot-2", "title": "B"},
        ],
    }

    updated = update_dashboard_plot(
        dashboard,
        "plot-2",
        {"id": "plot-2", "title": "Updated"},
    )

    assert updated["plots"][0]["title"] == "A"
    assert updated["plots"][1]["title"] == "Updated"


def test_remove_dashboard_plot_drops_matching_plot():
    dashboard = {
        "id": "dash-1",
        "name": "Main",
        "plots": [
            {"id": "plot-1", "title": "A"},
            {"id": "plot-2", "title": "B"},
        ],
    }

    updated = remove_dashboard_plot(dashboard, "plot-1")

    assert updated["plots"] == [{"id": "plot-2", "title": "B"}]
