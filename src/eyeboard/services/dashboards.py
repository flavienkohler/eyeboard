"""Loading, saving and editing the saved dashboards."""

import logging
from pathlib import Path

from eyeboard.dashboards.document import (
    LoadResult,
    load_document_text,
    serialize_document,
)
from eyeboard.dashboards.model import Dashboard, PlotSpec
from eyeboard.paths import dashboards_file
from eyeboard.services.fileio import backup_file, write_text_atomic

LOGGER = logging.getLogger(__name__)


def load_dashboards(path: str | Path | None = None) -> LoadResult:
    """Read the saved dashboards; a missing file simply means there are none."""
    file_path = Path(path) if path else dashboards_file()
    if not file_path.exists():
        return LoadResult()

    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:  # ValueError covers bad UTF-8
        result = LoadResult(blocked=True)
        result.problems.append(f"Could not read `{file_path}`: {exc}")
        return result

    result = load_document_text(text)
    if result.skipped:
        result.problems.append(
            "Entries that could not be loaded stay in the file until the next save; "
            "a backup copy is then kept next to it (*.unreadable.bak)."
        )
    return result


def save_dashboards(
    dashboards: list[Dashboard],
    path: str | Path | None = None,
    *,
    loaded: LoadResult | None = None,
) -> str | None:
    """Write the dashboards to disk and return an error message, or ``None``.

    ``loaded`` is what was read at startup. It protects data the app could not
    represent: a file the app does not understand is never overwritten, a file
    in an older format is copied once to ``*.v1.bak`` before the first write in
    the new format, and entries that failed validation are copied to
    ``*.unreadable.bak`` before they disappear from the file.
    """
    file_path = Path(path) if path else dashboards_file()
    if loaded is not None and loaded.blocked:
        return (
            f"`{file_path}` was not saved because the existing file could not be "
            "understood; it was left untouched."
        )

    try:
        text = serialize_document(dashboards)
        if loaded is not None:
            if loaded.migrated:
                backup_file(file_path, f"v{loaded.source_version}")
            if loaded.skipped:
                backup_file(file_path, "unreadable")
        write_text_atomic(file_path, text)
    except (OSError, TypeError, ValueError) as exc:
        return f"Could not save dashboards to `{file_path}`: {exc}"

    if loaded is not None:
        # The file now holds the current format and no longer holds skipped entries.
        loaded.source_version = LoadResult().source_version
        loaded.skipped = []
    return None


def find_dashboard_by_name(
    dashboards: list[Dashboard],
    dashboard_name: str,
) -> Dashboard | None:
    """Find a saved dashboard by name using a case-insensitive match."""
    normalized_name = dashboard_name.strip().casefold()
    if not normalized_name:
        return None

    for dashboard in dashboards:
        if dashboard.name.strip().casefold() == normalized_name:
            return dashboard
    return None


def update_dashboard_plot(
    dashboard: Dashboard,
    plot_id: str,
    new_plot: PlotSpec,
) -> Dashboard:
    """Return a dashboard with one plot replaced by id."""
    return dashboard.model_copy(
        update={
            "plots": [
                new_plot if plot.id == plot_id else plot for plot in dashboard.plots
            ]
        }
    )


def remove_dashboard_plot(dashboard: Dashboard, plot_id: str) -> Dashboard:
    """Return a dashboard with one plot removed by id.

    Callers must keep at least one plot: a dashboard without plots is not valid.
    """
    return dashboard.model_copy(
        update={"plots": [plot for plot in dashboard.plots if plot.id != plot_id]}
    )


def add_plot_to_dashboards(
    dashboards: list[Dashboard],
    name: str,
    plot: PlotSpec,
) -> tuple[list[Dashboard], Dashboard, bool]:
    """Add a plot to the dashboard of that name, or create the dashboard.

    The name is matched ignoring case and surrounding spaces. Returns the new
    list, the dashboard that received the plot, and whether it was created.
    """
    existing = find_dashboard_by_name(dashboards, name)
    if existing is None:
        created = Dashboard(name=name, plots=[plot])
        return [*dashboards, created], created, True

    updated = existing.model_copy(update={"plots": [*existing.plots, plot]})
    return (
        [updated if d.id == existing.id else d for d in dashboards],
        updated,
        False,
    )


def move_dashboard_plot(dashboard: Dashboard, plot_id: str, offset: int) -> Dashboard:
    """Return a dashboard with one plot moved up (negative) or down (positive).

    A move past either end, or an unknown plot id, leaves the order unchanged.
    """
    plots = list(dashboard.plots)
    index = next((i for i, plot in enumerate(plots) if plot.id == plot_id), None)
    if index is None:
        return dashboard
    target = index + offset
    if not 0 <= target < len(plots):
        return dashboard
    plots[index], plots[target] = plots[target], plots[index]
    return dashboard.model_copy(update={"plots": plots})


def name_is_taken(
    dashboards: list[Dashboard], name: str, *, ignore_id: str | None = None
) -> bool:
    """Tell whether another dashboard already has this name (ignoring case)."""
    other = find_dashboard_by_name(dashboards, name)
    return other is not None and other.id != ignore_id


def unique_name(dashboards: list[Dashboard], name: str) -> str:
    """Return the name, or the name followed by (2), (3)... when it is taken."""
    candidate, number = name.strip(), 1
    while name_is_taken(dashboards, candidate):
        number += 1
        candidate = f"{name.strip()} ({number})"
    return candidate
