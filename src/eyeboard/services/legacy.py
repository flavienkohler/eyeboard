"""One-time import of the files older versions kept in the working directory."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from eyeboard.paths import dashboards_file, recent_dir, recent_index_file

LOGGER = logging.getLogger(__name__)

LEGACY_DASHBOARDS_NAME = "saved_configs.json"
LEGACY_RECENT_DIR = Path("data") / ".recent_csvs"


@dataclass(frozen=True, slots=True)
class LegacyImport:
    """What was copied from the old locations."""

    dashboards_from: Path | None = None
    recent_files: int = 0
    recent_from: Path | None = None

    @property
    def happened(self) -> bool:
        return self.dashboards_from is not None or self.recent_files > 0


def import_legacy_files(base: Path | None = None) -> LegacyImport:
    """Copy (never move) dashboards and recent files from ``base`` if needed.

    Earlier versions stored ``saved_configs.json`` and ``data/.recent_csvs`` in the
    directory the app was started from. Files are only copied when the new
    location does not exist yet, so this runs once and never overwrites.
    """
    base = base or Path.cwd()
    dashboards_from = None
    recent_from = None
    recent_files = 0

    legacy_dashboards = base / LEGACY_DASHBOARDS_NAME
    if legacy_dashboards.is_file() and not dashboards_file().exists():
        try:
            dashboards_file().parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_dashboards, dashboards_file())
            dashboards_from = legacy_dashboards
        except OSError:
            LOGGER.exception("Could not copy the legacy dashboards file.")

    legacy_recent = base / LEGACY_RECENT_DIR
    if (legacy_recent / "index.json").is_file() and not recent_index_file().exists():
        try:
            recent_dir().mkdir(parents=True, exist_ok=True)
            for source in legacy_recent.iterdir():
                if source.is_file():
                    shutil.copy2(source, recent_dir() / source.name)
                    recent_files += source.name != "index.json"
            recent_from = legacy_recent
        except OSError:
            LOGGER.exception("Could not copy the legacy recent files.")

    return LegacyImport(dashboards_from, recent_files, recent_from)
