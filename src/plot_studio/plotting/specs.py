"""Plot specification builders."""

import uuid
from typing import Any


def build_plot_spec_from_builder(
    *,
    title: str | None,
    x_col: str,
    y_cols: list[str],
    plot_type: str,
    template: str,
    enable_secondary_axis: bool,
    y2_cols: list[str],
    yaxis_title_1: str | None,
    yaxis_title_2: str | None,
    color_col: str | None,
    agg: str | None,
    series_style: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a serializable plot specification from builder inputs."""
    return {
        "id": str(uuid.uuid4()),
        "title": title or None,
        "x_col": x_col,
        "y_cols": y_cols,
        "y2_cols": y2_cols if enable_secondary_axis else [],
        "plot_type": plot_type,
        "template": template,
        "yaxis_title_1": yaxis_title_1 or None,
        "yaxis_title_2": yaxis_title_2 or None,
        "color_col": color_col or None,
        "agg": agg or None,
        "series_style": series_style or {},
    }
