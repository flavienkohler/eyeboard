"""Template persistence helpers."""

import json
from pathlib import Path
from typing import Any

from plot_studio.config import DASHBOARDS_FILE
from plot_studio.services.fileio import write_text_atomic


def load_dashboards(
    path: str | Path = DASHBOARDS_FILE,
) -> tuple[list[dict[str, Any]], str | None]:
    """Load saved dashboards from disk."""
    config_path = Path(path)
    if not config_path.exists():
        return [], None

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError covers bad JSON and bad UTF-8
        return [], f"Could not read saved dashboards from `{config_path}`: {exc}"

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], None
    return [], f"Saved dashboards file `{config_path}` must contain a JSON list."


def save_dashboards(
    dashboards: list[dict[str, Any]],
    path: str | Path = DASHBOARDS_FILE,
) -> str | None:
    """Save the dashboards to disk."""
    config_path = Path(path)
    try:
        write_text_atomic(
            config_path, json.dumps(dashboards, ensure_ascii=False, indent=2)
        )
        return None
    except (OSError, TypeError, ValueError) as exc:
        return f"Could not save dashboards to `{config_path}`: {exc}"


def validate_dashboard(dashboard: dict[str, Any]) -> list[str]:
    """Validate the minimal structure required for a saved dashboard."""
    errors: list[str] = []

    config_name = dashboard.get("name")
    if config_name is not None and not isinstance(config_name, str):
        errors.append("`name` must be a string when present.")

    plots = dashboard.get("plots")
    if not isinstance(plots, list):
        errors.append("`plots` must be a list.")
        return errors

    if not plots:
        errors.append("`plots` is empty.")
        return errors

    for idx, plot in enumerate(plots, start=1):
        if not isinstance(plot, dict):
            errors.append(f"Plot {idx} must be an object.")
            continue

        x_col = plot.get("x_col")
        if not isinstance(x_col, str) or not x_col.strip():
            errors.append(f"Plot {idx} is missing a valid `x_col`.")

        y_cols = plot.get("y_cols")
        y2_cols = plot.get("y2_cols", [])
        if not isinstance(y_cols, list):
            errors.append(f"Plot {idx} has an invalid `y_cols` value.")
        if not isinstance(y2_cols, list):
            errors.append(f"Plot {idx} has an invalid `y2_cols` value.")

        valid_y_cols = isinstance(y_cols, list) and any(
            isinstance(col, str) and col.strip() for col in y_cols
        )
        valid_y2_cols = isinstance(y2_cols, list) and any(
            isinstance(col, str) and col.strip() for col in y2_cols
        )
        if not valid_y_cols and not valid_y2_cols:
            errors.append(f"Plot {idx} must define at least one Y series.")

    return errors


def find_dashboard_by_name(
    dashboards: list[dict[str, Any]],
    dashboard_name: str,
) -> dict[str, Any] | None:
    """Find a saved dashboard by name using a case-insensitive match."""
    normalized_name = dashboard_name.strip().casefold()
    if not normalized_name:
        return None

    for dashboard in dashboards:
        config_name = dashboard.get("name")
        if (
            isinstance(config_name, str)
            and config_name.strip().casefold() == normalized_name
        ):
            return dashboard
    return None


def update_dashboard_plot(
    dashboard: dict[str, Any],
    plot_id: str,
    new_plot: dict[str, Any],
) -> dict[str, Any]:
    """Return a dashboard with one plot replaced by id."""
    updated_dashboard = dict(dashboard)
    updated_plots: list[dict[str, Any]] = []

    for plot in dashboard.get("plots") or []:
        if isinstance(plot, dict) and plot.get("id") == plot_id:
            updated_plots.append(new_plot)
        else:
            updated_plots.append(plot)

    updated_dashboard["plots"] = updated_plots
    return updated_dashboard


def remove_dashboard_plot(
    dashboard: dict[str, Any],
    plot_id: str,
) -> dict[str, Any]:
    """Return a dashboard with one plot removed by id."""
    updated_dashboard = dict(dashboard)
    updated_dashboard["plots"] = [
        plot
        for plot in (dashboard.get("plots") or [])
        if not (isinstance(plot, dict) and plot.get("id") == plot_id)
    ]
    return updated_dashboard
