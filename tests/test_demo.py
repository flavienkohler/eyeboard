import io
from pathlib import Path

import pandas as pd

from eyeboard.models import ReadOptions
from eyeboard.services.dataset import load_table
from eyeboard.services.demo import DEMO_FILES, demo_csv, demo_source, write_examples

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_the_demo_data_is_identical_on_every_call():
    assert demo_csv("station_a") == demo_csv("station_a")
    assert demo_csv("station_a") != demo_csv("station_b")


def test_the_committed_examples_match_the_generator():
    for name, filename in DEMO_FILES.items():
        committed = pd.read_csv(EXAMPLES / filename)
        generated = pd.read_csv(io.BytesIO(demo_csv(name)))
        try:
            pd.testing.assert_frame_equal(committed, generated, atol=1e-3)
        except AssertionError as exc:
            raise AssertionError(
                f"{filename} is out of date: run `python -m eyeboard.services.demo examples`"
            ) from exc


def test_the_demo_files_load_like_any_csv_and_show_what_explore_checks():
    table, report = load_table(demo_source("station_a"), ReadOptions())

    assert len(table) == 24 * 60 and report.warnings == []
    assert report.separator_label == "Auto-detected Comma (,)"
    assert table["humidity_pct"].isna().sum() == 40
    assert table["flow_m3s"].isna().sum() == 21  # the maintenance window
    assert set(table["site"]) == {"demo"}  # a constant column


def test_station_b_is_a_biased_late_version_of_the_same_period():
    a, _ = load_table(demo_source("station_a"), ReadOptions())
    b, _ = load_table(demo_source("station_b"), ReadOptions())

    assert list(a["timestamp"]) == list(b["timestamp"])
    assert "humidity_pct" not in b.columns
    assert b["flow_m3s"].mean() > a["flow_m3s"].mean()


def test_write_examples_writes_both_files(tmp_path):
    paths = write_examples(tmp_path / "out")

    assert sorted(p.name for p in paths) == sorted(DEMO_FILES.values())
    assert pd.read_csv(paths[0]).shape[0] == 24 * 60
