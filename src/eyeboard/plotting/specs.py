"""Plot specification builders."""

from typing import Any

from eyeboard.dashboards.model import PlotSpec


def build_plot_spec_from_builder(
    *,
    title: str | None,
    x_col: str,
    y_cols: list[str],
    plot_type: str,
    theme: str,
    enable_secondary_axis: bool,
    y2_cols: list[str],
    yaxis_title_1: str | None,
    yaxis_title_2: str | None,
    color_col: str | None,
    agg: str | None,
    series_style: dict[str, dict[str, Any]] | None = None,
) -> PlotSpec:
    """Create a validated plot specification from the Plot Builder inputs.

    Raises ``pydantic.ValidationError`` when the inputs do not form a valid plot.
    """
    return PlotSpec.model_validate(
        {
            "title": title,
            "x_col": x_col,
            "y_cols": y_cols,
            "y2_cols": y2_cols if enable_secondary_axis else [],
            "plot_type": plot_type,
            "theme": theme,
            "yaxis_title_1": yaxis_title_1,
            "yaxis_title_2": yaxis_title_2,
            "color_col": color_col,
            "agg": agg,
            "series_style": series_style or {},
        }
    )
