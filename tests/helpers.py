"""Small builders shared by the tests."""

from eyeboard.dashboards.model import Dashboard, PlotSpec


def make_plot(**overrides) -> PlotSpec:
    """Build a valid plot, overriding any field."""
    fields = {"x_col": "date", "y_cols": ["value"]}
    fields.update(overrides)
    return PlotSpec.model_validate(fields)


def make_dashboard(
    id: str = "dashboard-1", name: str = "Board", **overrides
) -> Dashboard:
    """Build a valid dashboard with one plot, overriding any field."""
    fields = {"id": id, "name": name, "plots": [make_plot()]}
    fields.update(overrides)
    return Dashboard.model_validate(fields)
