"""Recent CSV cache helpers."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from plot_studio.config import (
    RECENT_CSV_CACHE_DIR,
    RECENT_CSV_INDEX_FILE,
    RECENT_CSV_LIMIT,
)


def load_recent_csv_index(
    path: Path = RECENT_CSV_INDEX_FILE,
) -> list[dict[str, Any]]:
    """Load recent CSV metadata from disk."""
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_recent_csv_index(
    entries: list[dict[str, Any]],
    path: Path = RECENT_CSV_INDEX_FILE,
) -> None:
    """Persist recent CSV metadata to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_filename(filename: str) -> str:
    """Create a safe filesystem name while keeping the extension readable."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return safe or "recent.csv"


def format_recent_csv_details(entry: dict[str, Any]) -> str:
    """Build a compact UI label for a recent CSV entry."""
    file_size = int(entry.get("file_size", 0) or 0)
    if file_size >= 1024**2:
        size_label = f"{file_size / (1024**2):.1f} MB"
    else:
        size_label = f"{file_size / 1024:.0f} KB"

    opened_at = entry.get("opened_at", "")
    try:
        opened_label = datetime.fromisoformat(opened_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        opened_label = opened_at or "unknown time"

    return f"{size_label} • {opened_label}"


def get_recent_csv_cache_path(
    entry_id: str,
    *,
    cache_dir: Path = RECENT_CSV_CACHE_DIR,
    index_path: Path = RECENT_CSV_INDEX_FILE,
) -> Path:
    """Return the cached file path for a recent CSV id."""
    entries = load_recent_csv_index(index_path)
    for entry in entries:
        if entry.get("id") == entry_id:
            filename = entry.get("cache_filename")
            if filename:
                return cache_dir / filename
            break
    return cache_dir / entry_id


def get_recent_csv_entry(
    entry_id: str,
    *,
    index_path: Path = RECENT_CSV_INDEX_FILE,
) -> dict[str, Any] | None:
    """Return the recent CSV metadata entry for a given id."""
    entries = load_recent_csv_index(index_path)
    return next((entry for entry in entries if entry.get("id") == entry_id), None)


def list_recent_csvs(
    limit: int = RECENT_CSV_LIMIT,
    *,
    cache_dir: Path = RECENT_CSV_CACHE_DIR,
    index_path: Path = RECENT_CSV_INDEX_FILE,
) -> list[dict[str, Any]]:
    """Return recent CSV entries newest first, pruning missing files."""
    entries = load_recent_csv_index(index_path)
    valid_entries: list[dict[str, Any]] = []
    changed = False

    for entry in sorted(entries, key=lambda item: item.get("opened_at", ""), reverse=True):
        cache_filename = entry.get("cache_filename")
        if not cache_filename:
            changed = True
            continue
        cache_path = cache_dir / cache_filename
        if cache_path.exists():
            valid_entries.append(entry)
        else:
            changed = True

    valid_entries = valid_entries[:limit]
    if changed or len(valid_entries) != len(entries):
        save_recent_csv_index(valid_entries, index_path)
    return valid_entries


def remember_recent_csv(
    filename: str,
    raw_bytes: bytes,
    *,
    cache_dir: Path = RECENT_CSV_CACHE_DIR,
    index_path: Path = RECENT_CSV_INDEX_FILE,
    max_items: int = RECENT_CSV_LIMIT,
) -> dict[str, Any]:
    """Cache a CSV locally and move it to the top of the recent list."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
    safe_name = sanitize_filename(filename)
    cache_filename = f"{digest}_{safe_name}"
    cache_path = cache_dir / cache_filename
    cache_path.write_bytes(raw_bytes)

    opened_at = datetime.now().isoformat(timespec="seconds")
    new_entry = {
        "id": digest,
        "filename": filename,
        "cache_filename": cache_filename,
        "file_size": len(raw_bytes),
        "opened_at": opened_at,
    }

    previous_entries = load_recent_csv_index(index_path)
    remaining_entries = [
        entry for entry in previous_entries if entry.get("id") != digest
    ]
    new_entries = [new_entry, *remaining_entries]
    pruned_entries = new_entries[:max_items]

    kept_ids = {entry.get("id") for entry in pruned_entries}
    for entry in previous_entries:
        entry_id = entry.get("id")
        cache_filename = entry.get("cache_filename")
        if entry_id in kept_ids or not cache_filename:
            continue
        stale_path = cache_dir / cache_filename
        if stale_path.exists():
            stale_path.unlink(missing_ok=True)

    save_recent_csv_index(pruned_entries, index_path)
    return new_entry


def touch_recent_csv(
    entry_id: str,
    *,
    index_path: Path = RECENT_CSV_INDEX_FILE,
    max_items: int = RECENT_CSV_LIMIT,
) -> dict[str, Any] | None:
    """Move an existing recent CSV entry to the top after reopening it."""
    entries = load_recent_csv_index(index_path)
    matching_entry = next((entry for entry in entries if entry.get("id") == entry_id), None)
    if matching_entry is None:
        return None

    updated_entry = dict(matching_entry)
    updated_entry["opened_at"] = datetime.now().isoformat(timespec="seconds")
    remaining_entries = [
        entry for entry in entries if entry.get("id") != entry_id
    ]
    save_recent_csv_index([updated_entry, *remaining_entries][:max_items], index_path)
    return updated_entry
