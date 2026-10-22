import json

from helpers import make_dashboard, make_plot

from eyeboard.dashboards.document import SCHEMA_VERSION
from eyeboard.services.dashboards import (
    add_plot_to_dashboards,
    find_dashboard_by_name,
    load_dashboards,
    remove_dashboard_plot,
    save_dashboards,
    update_dashboard_plot,
)


def test_dashboard_persistence_round_trip(tmp_path):
    path = tmp_path / "dashboards.json"
    dashboards = [make_dashboard("dashboard-1", "Main dashboard")]

    assert save_dashboards(dashboards, path) is None
    loaded = load_dashboards(path)

    assert loaded.dashboards == dashboards
    assert loaded.problems == [] and not loaded.migrated
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == (
        SCHEMA_VERSION
    )


def test_a_missing_file_means_no_dashboards(tmp_path):
    loaded = load_dashboards(tmp_path / "missing.json")

    assert loaded.dashboards == [] and loaded.problems == [] and not loaded.blocked


def test_invalid_json_blocks_the_file_and_is_reported(tmp_path):
    path = tmp_path / "dashboards.json"
    path.write_text("{not-valid-json", encoding="utf-8")

    loaded = load_dashboards(path)

    assert loaded.blocked and loaded.dashboards == []
    assert "not valid JSON" in loaded.problems[0]


def test_a_legacy_list_is_loaded_and_saved_in_the_new_format_with_a_backup(tmp_path):
    path = tmp_path / "saved_configs.json"
    legacy = [
        {
            "id": "d1",
            "name": "old",
            "plots": [{"x_col": "date", "y_cols": ["q"], "template": "plotly_dark"}],
        }
    ]
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_dashboards(path)
    assert loaded.migrated and loaded.dashboards[0].plots[0].theme == "plotly_dark"

    assert save_dashboards(loaded.dashboards, path, loaded=loaded) is None

    backup = tmp_path / "saved_configs.json.v1.bak"
    assert json.loads(backup.read_text(encoding="utf-8")) == legacy
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == (
        SCHEMA_VERSION
    )
    assert not loaded.migrated  # the load state reflects what is on disk now


def test_entries_that_failed_validation_are_backed_up_before_they_disappear(tmp_path):
    path = tmp_path / "saved_configs.json"
    good = {"id": "d1", "name": "ok", "plots": [{"x_col": "t", "y_cols": ["q"]}]}
    bad = {"id": "d2", "name": "broken", "plots": [{"x_col": "t"}]}
    path.write_text(json.dumps([good, bad]), encoding="utf-8")

    loaded = load_dashboards(path)
    assert [d.name for d in loaded.dashboards] == ["ok"] and loaded.skipped == [bad]
    assert any("backup" in problem for problem in loaded.problems)

    save_dashboards(loaded.dashboards, path, loaded=loaded)

    backup = json.loads((tmp_path / "saved_configs.json.unreadable.bak").read_text())
    assert bad in backup


def test_a_file_that_cannot_be_understood_is_never_overwritten(tmp_path):
    path = tmp_path / "dashboards.json"
    path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION + 1, "dashboards": []}),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    loaded = load_dashboards(path)
    error = save_dashboards([make_dashboard()], path, loaded=loaded)

    assert loaded.blocked
    assert error is not None and "left untouched" in error
    assert path.read_text(encoding="utf-8") == original


def test_find_dashboard_by_name_matches_case_insensitively():
    dashboards = [make_dashboard("dashboard-1", "Sensor Board")]

    match = find_dashboard_by_name(dashboards, "  sensor board  ")

    assert match is not None and match.id == "dashboard-1"
    assert find_dashboard_by_name(dashboards, "missing") is None
    assert find_dashboard_by_name(dashboards, "   ") is None


def test_update_dashboard_plot_replaces_matching_plot_only():
    first, second = make_plot(id="plot-1"), make_plot(id="plot-2", title="old")
    dashboard = make_dashboard(plots=[first, second])
    replacement = make_plot(id="plot-2", title="new")

    updated = update_dashboard_plot(dashboard, "plot-2", replacement)

    assert [p.title for p in updated.plots] == [None, "new"]
    assert dashboard.plots[1].title == "old"  # the original is not modified


def test_remove_dashboard_plot_drops_matching_plot():
    dashboard = make_dashboard(plots=[make_plot(id="plot-1"), make_plot(id="plot-2")])

    updated = remove_dashboard_plot(dashboard, "plot-1")

    assert [p.id for p in updated.plots] == ["plot-2"]


def test_add_plot_to_dashboards_appends_to_a_dashboard_of_the_same_name():
    board = make_dashboard("d1", "Sensor Board")
    plot = make_plot(id="new-plot")

    dashboards, target, created = add_plot_to_dashboards(
        [board], " sensor board ", plot
    )

    assert not created and target.id == "d1"
    assert [p.id for p in target.plots] == [board.plots[0].id, "new-plot"]
    assert dashboards == [target]
    assert len(board.plots) == 1  # the original is not modified


def test_add_plot_to_dashboards_creates_a_new_dashboard_for_a_new_name():
    board = make_dashboard("d1", "Sensor Board")

    dashboards, target, created = add_plot_to_dashboards([board], "Other", make_plot())

    assert created and target.name == "Other"
    assert dashboards == [board, target]
