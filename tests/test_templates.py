import json
import shutil
import uuid
from pathlib import Path

from plot_studio.services.templates import (
    find_saved_config_by_name,
    load_saved_configs_from_disk,
    remove_dashboard_plot,
    persist_saved_configs_to_disk,
    update_dashboard_plot,
    validate_saved_config,
)


def make_workspace_temp_dir() -> Path:
    temp_dir = Path("tests") / "_tmp" / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_template_persistence_round_trip():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        configs = [{"id": "cfg-1", "name": "Main dashboard", "plots": []}]

        save_error = persist_saved_configs_to_disk(configs, config_path)
        assert save_error is None

        loaded, load_error = load_saved_configs_from_disk(config_path)
        assert load_error is None
        assert loaded == configs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_load_saved_configs_filters_non_dict_items():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        config_path.write_text(
            json.dumps([{"id": "cfg-1"}, "bad-entry", 42]),
            encoding="utf-8",
        )

        loaded, load_error = load_saved_configs_from_disk(config_path)
        assert load_error is None
        assert loaded == [{"id": "cfg-1"}]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_load_saved_configs_reports_invalid_json():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        config_path.write_text("{not-valid-json", encoding="utf-8")

        loaded, load_error = load_saved_configs_from_disk(config_path)

        assert loaded == []
        assert load_error is not None
        assert "Could not read saved templates" in load_error
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_validate_saved_config_reports_missing_plot_series():
    config = {
        "id": "cfg-1",
        "name": "Broken template",
        "plots": [{"x_col": "time", "y_cols": [], "y2_cols": []}],
    }

    errors = validate_saved_config(config)

    assert "Plot 1 must define at least one Y series." in errors


def test_validate_saved_config_accepts_minimal_valid_template():
    config = {
        "id": "cfg-1",
        "name": "Valid template",
        "plots": [{"x_col": "time", "y_cols": ["value"], "y2_cols": []}],
    }

    errors = validate_saved_config(config)

    assert errors == []


def test_find_saved_config_by_name_matches_case_insensitively():
    configs = [
        {"id": "cfg-1", "name": "Sensor Board", "plots": []},
        {"id": "cfg-2", "name": "Meteo", "plots": []},
    ]

    match = find_saved_config_by_name(configs, "  sensor board  ")

    assert match is not None
    assert match["id"] == "cfg-1"


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
