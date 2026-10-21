"""Safe file writing helpers."""

import os
import shutil
import tempfile
from pathlib import Path


def write_text_atomic(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Write a text file so that readers never see a half-written file.

    The text goes to a temporary file in the same folder, which then replaces the
    target in one step (``os.replace`` is atomic on Windows and POSIX). If the
    process dies midway, the previous version of the file is still intact.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as tmp_file:
            tmp_file.write(text)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def backup_file(path: str | Path, tag: str, *, overwrite: bool = False) -> Path | None:
    """Copy a file next to itself as ``<name>.<tag>.bak``.

    Returns the backup path, or ``None`` when there is nothing to back up or the
    backup already exists and ``overwrite`` is false.
    """
    source = Path(path)
    if not source.exists():
        return None
    backup = source.with_name(f"{source.name}.{tag}.bak")
    if backup.exists() and not overwrite:
        return None
    shutil.copy2(source, backup)
    return backup
