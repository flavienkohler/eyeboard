import json

from eyeboard import paths
from eyeboard.services.legacy import import_legacy_files
from eyeboard.services.recent_csvs import (
    clear_recent_csvs,
    list_recent_csvs,
    remember_recent_csv,
)


def test_the_data_folder_comes_from_the_environment(eyeboard_home):
    assert paths.data_dir() == eyeboard_home
    assert paths.dashboards_file() == eyeboard_home / "dashboards.json"
    assert paths.recent_dir() == eyeboard_home / "recent"
    assert paths.recent_index_file() == eyeboard_home / "recent" / "index.json"


def test_without_the_variable_the_per_user_folder_is_used(monkeypatch):
    monkeypatch.delenv(paths.HOME_ENV_VAR)

    folder = paths.data_dir()

    assert folder.is_absolute() and folder.name.lower() == "eyeboard"


def test_the_location_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    before = paths.dashboards_file()

    monkeypatch.chdir(tmp_path)

    assert paths.dashboards_file() == before


def _write_legacy_files(base):
    (base / "saved_configs.json").write_text("[]", encoding="utf-8")
    recent = base / "data" / ".recent_csvs"
    recent.mkdir(parents=True)
    (recent / "abc_old.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (recent / "index.json").write_text(
        json.dumps(
            [{"id": "abc", "filename": "old.csv", "cache_filename": "abc_old.csv"}]
        ),
        encoding="utf-8",
    )


def test_legacy_files_are_copied_not_moved(tmp_path, eyeboard_home):
    _write_legacy_files(tmp_path)

    result = import_legacy_files(tmp_path)

    assert result.happened and result.recent_files == 1
    assert (eyeboard_home / "dashboards.json").read_text(encoding="utf-8") == "[]"
    assert (eyeboard_home / "recent" / "abc_old.csv").exists()
    assert (tmp_path / "saved_configs.json").exists()  # the originals stay
    assert (tmp_path / "data" / ".recent_csvs" / "index.json").exists()


def test_legacy_files_never_overwrite_the_new_ones(tmp_path, eyeboard_home):
    _write_legacy_files(tmp_path)
    (eyeboard_home / "recent").mkdir(parents=True)
    (eyeboard_home / "recent" / "index.json").write_text("[]", encoding="utf-8")
    (eyeboard_home / "dashboards.json").write_text("mine", encoding="utf-8")

    result = import_legacy_files(tmp_path)

    assert not result.happened
    assert (eyeboard_home / "dashboards.json").read_text(encoding="utf-8") == "mine"
    assert not (eyeboard_home / "recent" / "abc_old.csv").exists()


def test_nothing_happens_when_there_are_no_legacy_files(tmp_path):
    assert not import_legacy_files(tmp_path).happened


def test_clear_recent_csvs_removes_files_and_index():
    remember_recent_csv("one.csv", b"a\n1\n")
    remember_recent_csv("two.csv", b"a\n2\n")
    assert len(list_recent_csvs()) == 2

    removed = clear_recent_csvs()

    assert removed == 2
    assert list_recent_csvs() == []
    assert not paths.recent_index_file().exists()
    assert list(paths.recent_dir().iterdir()) == []


def test_an_index_cannot_point_outside_the_cache_folder(eyeboard_home):
    from eyeboard.services.recent_csvs import get_recent_csv_cache_path

    (eyeboard_home / "recent").mkdir(parents=True)
    (eyeboard_home / "recent" / "index.json").write_text(
        json.dumps(
            [{"id": "x", "filename": "x.csv", "cache_filename": "../../secret.csv"}]
        ),
        encoding="utf-8",
    )

    cached = get_recent_csv_cache_path("x")

    assert cached.parent == eyeboard_home / "recent" and cached.name == "secret.csv"
