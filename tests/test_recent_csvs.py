import shutil
import uuid
from pathlib import Path

from plot_studio.services.recent_csvs import (
    get_recent_csv_cache_path,
    list_recent_csvs,
    remember_recent_csv,
    touch_recent_csv,
)


def make_workspace_temp_dir() -> Path:
    temp_dir = Path("tests") / "_tmp" / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_remember_recent_csv_persists_and_sorts_entries():
    temp_dir = make_workspace_temp_dir()
    try:
        cache_dir = temp_dir / "recent"
        index_path = cache_dir / "index.json"

        first = remember_recent_csv(
            "first.csv",
            b"a,b\n1,2\n",
            cache_dir=cache_dir,
            index_path=index_path,
            max_items=10,
        )
        second = remember_recent_csv(
            "second.csv",
            b"a,b\n3,4\n",
            cache_dir=cache_dir,
            index_path=index_path,
            max_items=10,
        )

        entries = list_recent_csvs(limit=10, cache_dir=cache_dir, index_path=index_path)

        assert len(entries) == 2
        assert entries[0]["id"] == second["id"]
        assert entries[1]["id"] == first["id"]
        assert entries[0]["filename"] == "second.csv"
        assert (cache_dir / first["cache_filename"]).exists()
        assert (cache_dir / second["cache_filename"]).exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_list_recent_csvs_prunes_missing_files():
    temp_dir = make_workspace_temp_dir()
    try:
        cache_dir = temp_dir / "recent"
        index_path = cache_dir / "index.json"
        entry = remember_recent_csv(
            "first.csv",
            b"a,b\n1,2\n",
            cache_dir=cache_dir,
            index_path=index_path,
            max_items=10,
        )
        (cache_dir / entry["cache_filename"]).unlink()

        entries = list_recent_csvs(limit=10, cache_dir=cache_dir, index_path=index_path)

        assert entries == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_touch_recent_csv_moves_entry_to_front():
    temp_dir = make_workspace_temp_dir()
    try:
        cache_dir = temp_dir / "recent"
        index_path = cache_dir / "index.json"
        first = remember_recent_csv(
            "first.csv",
            b"a,b\n1,2\n",
            cache_dir=cache_dir,
            index_path=index_path,
            max_items=10,
        )
        second = remember_recent_csv(
            "second.csv",
            b"a,b\n3,4\n",
            cache_dir=cache_dir,
            index_path=index_path,
            max_items=10,
        )

        updated = touch_recent_csv(second["id"], index_path=index_path, max_items=10)
        cache_path = get_recent_csv_cache_path(
            updated["id"],
            cache_dir=cache_dir,
            index_path=index_path,
        )

        assert updated is not None
        assert updated["id"] == second["id"]
        assert cache_path.exists()
        assert get_recent_csv_cache_path(
            first["id"],
            cache_dir=cache_dir,
            index_path=index_path,
        ).exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
