"""Run the whole Streamlit app headlessly (no browser) on a small file."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "eyeboard" / "streamlit_app.py"
CSV = "date;flow;temp\n" + "".join(
    f"{day:02d}/03/2020;{day * 0.5:.1f};{day * 0.25:.2f}\n".replace(".", ",")
    for day in range(1, 29)
)


@pytest.fixture
def workdir(eyeboard_home, tmp_path, monkeypatch):
    """The data folder with one recent CSV, so the app has data to show."""
    cache = eyeboard_home / "recent"
    cache.mkdir(parents=True)
    (cache / "abc_small.csv").write_text(CSV, encoding="utf-8")
    (cache / "index.json").write_text(
        json.dumps(
            [
                {
                    "id": "abc",
                    "filename": "small.csv",
                    "cache_filename": "abc_small.csv",
                    "file_size": len(CSV),
                    "opened_at": "2026-10-21T10:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)  # unrelated to the data folder
    return eyeboard_home


def _run(select_recent: bool) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    if select_recent:
        at.session_state["active_csv_source"] = "recent"
        at.session_state["active_recent_csv_id"] = "abc"
    return at.run()


def test_without_a_file_the_app_asks_for_one(workdir):
    at = _run(select_recent=False)

    assert not at.exception
    assert "Upload a CSV to start, or try the demo data from the sidebar." in [
        info.value for info in at.info
    ]


def test_with_a_file_every_tab_renders_without_errors(workdir):
    at = _run(select_recent=True)

    assert not at.exception and not at.error
    assert [tab.label for tab in at.tabs][:3] == [
        "Explore",
        "Plot",
        "Dashboards",
    ]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rows"] == "28" and metrics["Columns"] == "3"
    assert metrics["Encoding"] == "UTF-8 (auto)"
    assert metrics["Separator"] == "Semicolon (;) (auto)"
    assert metrics["Date order"] == "day first (auto)"
    assert "Date parsing" in [e.label for e in at.sidebar.expander]


def test_the_sidebar_shows_the_loaded_file_and_no_dashboard_picker(workdir):
    at = _run(select_recent=True)

    captions = [c.value for c in at.sidebar.caption]
    assert "28 rows x 3 columns" in captions
    assert "Dates parsed: 100%" in captions
    assert any("Separator: Semicolon (;) (auto)" in c for c in captions)
    assert "Active dashboard" not in [s.label for s in at.sidebar.selectbox]


def test_explore_flags_numbers_written_with_a_decimal_comma(workdir):
    at = _run(select_recent=True)

    warnings = [w.value for w in at.warning]
    assert any("decimal comma" in w and "`flow`" in w for w in warnings)


def test_explore_lists_every_column_with_its_checks(workdir):
    at = _run(select_recent=True)

    frames = [df.value for df in at.dataframe]
    columns_table = next(f for f in frames if "distinct" in f.columns)
    assert list(columns_table["column"]) == ["date", "flow", "temp"]
    assert columns_table.loc[0, "type"] == "date"


def test_searching_columns_filters_the_table(workdir):
    at = _run(select_recent=True)

    next(t for t in at.text_input if t.label == "Search columns").input("flo").run()

    frames = [df.value for df in at.dataframe]
    columns_table = next(f for f in frames if "distinct" in f.columns)
    assert list(columns_table["column"]) == ["flow"]


def _saved_dashboards(workdir):
    path = workdir / "dashboards.json"
    return json.loads(path.read_text(encoding="utf-8"))["dashboards"]


def _save_plot(at, name="My board"):
    next(t for t in at.text_input if t.label == "Dashboard name").input(name).run()
    next(b for b in at.button if b.label == "Save to dashboard").click().run()
    at.run()  # AppTest keeps stale elements after st.rerun(); this run clears them


def test_the_plot_tab_draws_a_preview_and_keeps_styling_out_of_the_sidebar(workdir):
    at = _run(select_recent=True)

    assert not at.exception and not at.error
    assert "plot_preview" in _chart_keys(at)
    assert not list(at.sidebar.color_picker)


def test_a_plot_is_saved_without_series_styles_unless_customized(workdir):
    at = _run(select_recent=True)

    _save_plot(at)

    assert not at.exception
    (dashboard,) = _saved_dashboards(workdir)
    assert dashboard["name"] == "My board"
    assert dashboard["plots"][0]["series_style"] == {}


def test_customized_series_styles_are_saved_with_the_plot(workdir):
    at = _run(select_recent=True)
    next(t for t in at.toggle if t.label == "Customize series").set_value(True).run()

    _save_plot(at)

    (dashboard,) = _saved_dashboards(workdir)
    style = dashboard["plots"][0]["series_style"]
    assert len(style) == 1
    assert next(iter(style.values()))["width"] == 2


def test_saving_twice_adds_a_second_plot_to_the_same_dashboard(workdir):
    at = _run(select_recent=True)
    _save_plot(at)

    next(b for b in at.button if b.label == "Save to dashboard").click().run()

    (dashboard,) = _saved_dashboards(workdir)
    assert len(dashboard["plots"]) == 2
    assert dashboard["plots"][0]["id"] != dashboard["plots"][1]["id"]


def test_a_saved_plot_is_edited_with_the_same_form_filled_in(workdir):
    _add_dashboard_and_second_csv(workdir)
    at = _run(select_recent=True)
    assert not any((m.key or "").startswith("edit_") for m in at.multiselect)

    next(b for b in at.button if b.label == "Edit").click().run()
    y_axis = next(
        m
        for m in at.multiselect
        if (m.key or "").startswith("edit_") and (m.key or "").endswith("_y")
    )
    assert y_axis.value == ["flow"]
    title = next(
        t
        for t in at.text_input
        if (t.key or "").startswith("edit_") and t.label.startswith("Plot title")
    )
    title.input("Edited").run()
    next(b for b in at.button if b.label == "Save plot changes").click().run()

    (dashboard,) = _saved_dashboards(workdir)
    assert dashboard["plots"][0]["title"] == "Edited"
    assert dashboard["plots"][0]["y_cols"] == ["flow"]
    assert dashboard["plots"][0]["id"]  # the plot keeps its own id


def _two_plot_dashboard(workdir):
    from helpers import make_dashboard, make_plot

    from eyeboard.dashboards.document import serialize_document

    boards = [
        make_dashboard(
            "d1",
            "Flow board",
            plots=[
                make_plot(id="p1", title="First", x_col="date", y_cols=["flow"]),
                make_plot(id="p2", title="Second", x_col="date", y_cols=["temp"]),
            ],
        ),
        make_dashboard("d2", "Other board"),
    ]
    (workdir / "dashboards.json").write_text(
        serialize_document(boards), encoding="utf-8"
    )


def _plot_titles(workdir, index=0):
    return [p["title"] for p in _saved_dashboards(workdir)[index]["plots"]]


def test_plots_can_be_moved_within_a_dashboard(workdir):
    _two_plot_dashboard(workdir)
    at = _run(select_recent=True)

    next(b for b in at.button if b.key == "down_p1").click().run()

    assert _plot_titles(workdir) == ["Second", "First"]


def test_removing_a_plot_needs_the_confirmation_button(workdir):
    _two_plot_dashboard(workdir)
    at = _run(select_recent=True)
    assert _plot_titles(workdir) == ["First", "Second"]

    next(b for b in at.button if b.key == "confirm_rm_p1").click().run()

    assert _plot_titles(workdir) == ["Second"]


def test_deleting_a_dashboard_needs_the_confirmation_button(workdir):
    _two_plot_dashboard(workdir)
    at = _run(select_recent=True)
    assert len(_saved_dashboards(workdir)) == 2

    next(b for b in at.button if b.key == "confirm_delete_dashboard").click().run()

    assert [d["name"] for d in _saved_dashboards(workdir)] == ["Other board"]


def test_renaming_to_a_taken_name_is_refused(workdir):
    _two_plot_dashboard(workdir)
    at = _run(select_recent=True)

    next(t for t in at.text_input if t.label == "Rename").input("other BOARD").run()
    next(b for b in at.button if b.label == "Apply rename").click().run()

    assert any("already exists" in e.value for e in at.error)
    assert [d["name"] for d in _saved_dashboards(workdir)] == [
        "Flow board",
        "Other board",
    ]


def test_the_demo_button_loads_the_demo_data_without_remembering_it(workdir):
    at = _run(select_recent=False)

    next(b for b in at.sidebar.button if b.key == "try_demo").click().run()
    at.run()

    assert not at.exception and not at.error
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rows"] == "1,440" and metrics["Date order"] == "year first (auto)"
    assert not any("decimal comma" in w.value for w in at.warning)
    recent = json.loads((workdir / "recent" / "index.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in recent] == ["abc"]  # the demo was not added


def test_the_demo_files_can_be_compared_without_any_upload(workdir):
    at = _run(select_recent=False)
    next(b for b in at.sidebar.button if b.key == "try_demo").click().run()
    at.run()
    _save_demo_dashboard(workdir, at)

    next(s for s in at.selectbox if s.key == "compare_b_recent").select(
        "demo:station_b"
    ).run()

    table = next(df.value for df in at.dataframe if "bias (B - A)" in df.value.columns)
    assert list(table["series"]) == ["flow_m3s"]
    assert table.loc[0, "bias (B - A)"] > 0  # the model run is 6 % too high


def _save_demo_dashboard(workdir, at):
    from helpers import make_dashboard, make_plot

    at.session_state["dashboards"] = [
        make_dashboard(
            "d1",
            "Flow",
            plots=[make_plot(id="p1", x_col="timestamp", y_cols=["flow_m3s"])],
        )
    ]
    at.session_state["active_dashboard_id"] = "d1"
    at.run()


def _download_labels(at):
    return [b.proto.label for b in at.get("download_button")]


def test_export_files_are_prepared_only_when_asked_for(workdir):
    at = _run(select_recent=True)
    assert "Chart (HTML)" not in _download_labels(at)

    next(t for t in at.toggle if t.key == "plot_export").set_value(True).run()

    labels = _download_labels(at)
    assert "Chart (HTML)" in labels and "Plotted data (CSV)" in labels


def test_switching_to_french_translates_the_page_and_keeps_the_choices(workdir):
    at = _run(select_recent=True)
    next(s for s in at.sidebar.selectbox if s.key == "read_sep").select("Semicolon (;)")
    at.run()

    next(s for s in at.sidebar.selectbox if s.key == "language").select("fr").run()

    assert not at.exception and not at.error
    assert [tab.label for tab in at.tabs][:3] == [
        "Explorer",
        "Tracer",
        "Tableaux de bord",
    ]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Séparateur"] == "Point-virgule (;)"  # chosen, not detected
    assert metrics["Ordre des dates"] == "jour en premier (auto)"
    separator = next(s for s in at.sidebar.selectbox if s.key == "read_sep")
    assert separator.value == "Semicolon (;)"  # the choice survived the new label
    assert any("virgule décimale" in w.value for w in at.warning)


def test_the_date_column_is_detected_from_the_loaded_file(workdir):
    at = _run(select_recent=True)

    assert at.session_state["read_date_col"] == "date"


def test_a_broken_file_is_reported_not_raised(workdir):
    (workdir / "recent" / "abc_small.csv").write_bytes(b"")

    at = _run(select_recent=True)

    assert not at.exception
    assert any("Could not read CSV" in error.value for error in at.error)


def test_choosing_no_date_column_is_kept_across_reruns(workdir):
    at = _run(select_recent=True)
    picker = next(s for s in at.sidebar.selectbox if s.label.startswith("Date/time"))

    picker.set_value(None)
    at.run()

    assert not at.exception
    assert at.session_state["read_date_col"] is None


def _chart_keys(at: AppTest) -> set[str]:
    """Keys of the Plotly charts on the page (the key ends the element id)."""
    return {chart.proto.id.rsplit("-", 1)[-1] for chart in at.get("plotly_chart")}


def _add_dashboard_and_second_csv(workdir):
    from helpers import make_dashboard, make_plot

    from eyeboard.dashboards.document import serialize_document

    dashboard = make_dashboard(
        "d1", "Flow board", plots=[make_plot(id="p1", x_col="date", y_cols=["flow"])]
    )
    (workdir / "dashboards.json").write_text(
        serialize_document([dashboard]), encoding="utf-8"
    )
    cache = workdir / "recent"
    (cache / "def_other.csv").write_text(CSV.replace("1,0", "9,0"), encoding="utf-8")
    index_path = cache / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index.append(
        {
            "id": "def",
            "filename": "other.csv",
            "cache_filename": "def_other.csv",
            "file_size": 10,
            "opened_at": "2026-10-21T09:00:00Z",
        }
    )
    index_path.write_text(json.dumps(index), encoding="utf-8")


def test_the_dashboard_tab_draws_a_saved_dashboard_with_the_shared_dates(workdir):
    _add_dashboard_and_second_csv(workdir)

    at = _run(select_recent=True)

    assert not at.exception and not at.error
    assert "Flow board" in [d.name for d in at.session_state["dashboards"]]
    assert "dash_plot_d1" in _chart_keys(at)
    # The dashboard tab no longer has date controls of its own.
    labels = [w.label for w in at.selectbox] + [w.label for w in at.text_input]
    assert "Date/time column for dashboard (optional)" not in labels


def _compare_run(workdir):
    """The main file in the sidebar, the other recent file as B, decimal comma on."""
    _add_dashboard_and_second_csv(workdir)
    at = _run(select_recent=True)
    next(s for s in at.sidebar.selectbox if s.label == "Decimal").select("Comma (,)")
    at.run()
    next(s for s in at.selectbox if s.key == "compare_b_recent").select("def").run()
    return at


def test_compare_overlays_b_on_a_and_measures_the_gap(workdir):
    at = _compare_run(workdir)

    assert not at.exception and not at.error
    assert "cmp_d1_p1" in _chart_keys(at)
    table = next(df.value for df in at.dataframe if "bias (B - A)" in df.value.columns)
    assert list(table["series"]) == ["flow"]
    assert table.loc[0, "points"] > 0


def test_compare_can_show_two_charts_side_by_side(workdir):
    at = _compare_run(workdir)

    next(r for r in at.radio if r.key == "compare_mode").set_value("Side by side").run()

    assert {"cmp_d1_p1_A", "cmp_d1_p1_B"} <= _chart_keys(at)


def test_compare_draws_every_plot_of_a_dashboard(workdir):
    _two_plot_dashboard(workdir)
    cache = workdir / "recent"
    (cache / "def_other.csv").write_text(CSV, encoding="utf-8")
    index = json.loads((cache / "index.json").read_text(encoding="utf-8"))
    index.append(
        {
            "id": "def",
            "filename": "other.csv",
            "cache_filename": "def_other.csv",
            "file_size": 10,
            "opened_at": "2026-10-21T09:00:00Z",
        }
    )
    (cache / "index.json").write_text(json.dumps(index), encoding="utf-8")
    at = _run(select_recent=True)

    next(s for s in at.selectbox if s.key == "compare_b_recent").select("def").run()

    assert {"cmp_d1_p1", "cmp_d1_p2"} <= _chart_keys(at)


def test_files_of_an_older_version_are_imported_and_announced(
    eyeboard_home, tmp_path, monkeypatch
):
    from helpers import make_dashboard

    from eyeboard.dashboards.document import serialize_document

    old = tmp_path / "old_project"
    (old / "data" / ".recent_csvs").mkdir(parents=True)
    (old / "saved_configs.json").write_text(
        serialize_document([make_dashboard("d1", "Old board")]), encoding="utf-8"
    )
    monkeypatch.chdir(old)

    at = _run(select_recent=False)

    assert not at.exception
    assert [d.name for d in at.session_state["dashboards"]] == ["Old board"]
    assert any("now keeps its files" in info.value for info in at.info)
    assert (eyeboard_home / "dashboards.json").exists()


def test_clearing_the_recent_files_empties_the_list(workdir):
    at = _run(select_recent=True)
    assert any(b.label == "small.csv" for b in at.sidebar.button)

    next(b for b in at.sidebar.button if b.label == "Clear recent files").click()
    at.run()
    # AppTest keeps trailing elements of a shorter rerun; one more run drops them.
    at.run()

    assert not at.exception
    assert not any(b.label == "small.csv" for b in at.sidebar.button)
    assert not (workdir / "recent" / "abc_small.csv").exists()
