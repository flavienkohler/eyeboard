import json
import re

import pytest

from eyeboard.services.clock import utc_now_iso
from eyeboard.services.dashboards import save_dashboards
from eyeboard.services.fileio import backup_file, write_text_atomic
from eyeboard.services.recent_csvs import (
    format_recent_csv_details,
    load_recent_csv_index,
)


def test_write_text_atomic_creates_folders_and_writes_text(tmp_path):
    target = tmp_path / "nested" / "file.json"

    write_text_atomic(target, '{"a": 1}')

    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert [p.name for p in target.parent.iterdir()] == ["file.json"]


def test_write_text_atomic_keeps_the_old_file_when_the_write_fails(tmp_path):
    target = tmp_path / "file.json"
    target.write_text("old", encoding="utf-8")

    with pytest.raises(UnicodeEncodeError):
        write_text_atomic(target, "caf\u00e9", encoding="ascii")

    assert target.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["file.json"]


def test_persist_dashboards_reports_unserialisable_data_and_keeps_the_file(
    tmp_path,
):
    target = tmp_path / "saved.json"
    target.write_text("[]", encoding="utf-8")

    error = save_dashboards([{"bad": object()}], target)

    assert error is not None and "Could not save" in error
    assert json.loads(target.read_text(encoding="utf-8")) == []


def test_corrupt_recent_index_is_moved_aside_not_overwritten(tmp_path):
    index = tmp_path / "index.json"
    index.write_text("{not json", encoding="utf-8")

    assert load_recent_csv_index(index) == []

    assert not index.exists()
    assert (tmp_path / "index.json.corrupt").read_text(encoding="utf-8") == "{not json"


def test_utc_now_iso_has_a_z_suffix_and_second_precision():
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", utc_now_iso())


@pytest.mark.parametrize(
    "opened_at",
    ["2026-07-14T11:47:34", "2026-10-21T14:55:35Z", "not a date", ""],
)
def test_recent_details_accept_old_and_new_timestamp_formats(opened_at):
    label = format_recent_csv_details({"file_size": 2048, "opened_at": opened_at})

    assert label.startswith("2 KB")


def test_backup_file_copies_once_unless_overwrite_is_requested(tmp_path):
    source = tmp_path / "saved.json"
    source.write_text("v1", encoding="utf-8")

    first = backup_file(source, "v1")
    source.write_text("changed", encoding="utf-8")
    second = backup_file(source, "v1")
    third = backup_file(source, "v1", overwrite=True)

    assert first == tmp_path / "saved.json.v1.bak" and second is None
    assert third == first
    assert first.read_text(encoding="utf-8") == "changed"


def test_backup_file_ignores_a_missing_source(tmp_path):
    assert backup_file(tmp_path / "missing.json", "v1") is None
