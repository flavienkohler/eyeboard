"""Run the whole Streamlit app headlessly (no browser) on a small file."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "app.py"
CSV = "date;flow;temp\n" + "".join(
    f"{day:02d}/03/2020;{day * 0.5:.1f};{day * 0.25:.2f}\n".replace(".", ",")
    for day in range(1, 29)
)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """A scratch folder with one recent CSV, so the app has data to show."""
    cache = tmp_path / "data" / ".recent_csvs"
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
    monkeypatch.chdir(tmp_path)
    return tmp_path


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
        "Preview",
        "Plot Builder",
        "Dashboard",
    ]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rows"] == "28" and metrics["Columns"] == "3"
    assert metrics["Encoding"] == "UTF-8"
    assert "Date parsing" in [e.label for e in at.sidebar.expander]


def test_the_date_column_is_detected_from_the_loaded_file(workdir):
    at = _run(select_recent=True)

    assert at.session_state["read_date_col"] == "date"


def test_a_broken_file_is_reported_not_raised(workdir):
    (workdir / "data" / ".recent_csvs" / "abc_small.csv").write_bytes(b"")

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
