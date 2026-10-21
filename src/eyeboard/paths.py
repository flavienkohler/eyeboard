"""Where EyeBoard keeps its files.

Everything lives in one data folder, whatever the directory the app is started
from: ``$EYEBOARD_HOME`` if set, otherwise the standard per-user data folder of
the operating system (for example ``%APPDATA%/eyeboard`` on Windows).
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

HOME_ENV_VAR = "EYEBOARD_HOME"


def data_dir() -> Path:
    """Return the folder where dashboards and recent files are stored."""
    configured = os.environ.get(HOME_ENV_VAR, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(user_data_dir("eyeboard", appauthor=False))


def dashboards_file() -> Path:
    """Return the file holding the saved dashboards."""
    return data_dir() / "dashboards.json"


def recent_dir() -> Path:
    """Return the folder holding the copies of recently opened CSV files."""
    return data_dir() / "recent"


def recent_index_file() -> Path:
    """Return the file listing the recently opened CSV files."""
    return recent_dir() / "index.json"
