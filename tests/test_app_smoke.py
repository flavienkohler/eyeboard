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
    assert "Upload a CSV to start." in [info.value for info in at.info]


def test_with_a_file_every_tab_renders_without_errors(workdir):
    at = _run(select_recent=True)

    assert not at.exception and not at.error
    assert [tab.label for tab in at.tabs][:3] == [
        "Explore",
        "Plot Builder",
        "Dashboard",
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
        "d1", "Flow board", plots=[make_plot(x_col="date", y_cols=["flow"])]
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


def test_the_compare_tab_draws_both_datasets_with_the_shared_dates(workdir):
    _add_dashboard_and_second_csv(workdir)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["active_csv_source"] = "recent"
    at.session_state["active_recent_csv_id"] = "abc"
    at.session_state["cmp_recent_csv_a"] = "abc"
    at.session_state["cmp_recent_csv_b"] = "def"
    at.run()

    assert not at.exception and not at.error
    assert {"cmp_plot_a_d1", "cmp_plot_b_d1"} <= _chart_keys(at)
    labels = [w.label for w in at.selectbox]
    assert "Shared date/time column (optional)" not in labels


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
