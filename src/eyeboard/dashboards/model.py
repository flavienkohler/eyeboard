"""Typed models of dashboards and plots.

These models describe data that crosses a boundary (saved file, imported JSON,
the JSON editor). Data is parsed once, here; the rest of the app can then rely
on the shape instead of checking keys everywhere.
"""

import uuid
from typing import Annotated, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from eyeboard.config import THEMES
from eyeboard.services.clock import utc_now_iso

PlotType = Literal["Line", "Scatter", "Bar", "Area"]
Aggregation = Literal["mean", "sum", "min", "max", "median"]
DashStyle = Literal["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]

AGGREGATIONS = get_args(Aggregation)
DASH_STYLES = get_args(DashStyle)

ColumnName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def new_id() -> str:
    """Return a new unique identifier."""
    return str(uuid.uuid4())


class _Strict(BaseModel):
    """Base model: unknown keys are errors, so typos do not pass silently."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SeriesStyle(_Strict):
    """Look of one series."""

    color: str | None = None
    width: float | None = Field(default=None, gt=0, le=20)
    dash: DashStyle | None = None


class PlotSpec(_Strict):
    """Definition of one plot, independent of any dataset."""

    id: str = Field(default_factory=new_id)
    title: str | None = None
    x_col: ColumnName
    y_cols: list[ColumnName] = Field(default_factory=list)
    y2_cols: list[ColumnName] = Field(default_factory=list)
    plot_type: PlotType = "Line"
    theme: str = "plotly_white"
    yaxis_title_1: str | None = None
    yaxis_title_2: str | None = None
    color_col: str | None = None
    agg: Aggregation | None = None
    series_style: dict[str, SeriesStyle] = Field(default_factory=dict)

    @field_validator(
        "title", "yaxis_title_1", "yaxis_title_2", "color_col", "agg", mode="before"
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        """Treat empty strings as 'not set'."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("y_cols", "y2_cols", mode="before")
    @classmethod
    def _none_is_empty_list(cls, value: object) -> object:
        """Older files may store null for an unused axis."""
        return [] if value is None else value

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, value: str) -> str:
        if value not in THEMES:
            raise ValueError(f"unknown theme '{value}', expected one of {THEMES}")
        return value

    @model_validator(mode="after")
    def _has_a_series(self) -> "PlotSpec":
        if not self.y_cols and not self.y2_cols:
            raise ValueError("at least one Y series is required")
        return self


class Dashboard(_Strict):
    """A named collection of plots."""

    id: str = Field(default_factory=new_id)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    created_at: str = Field(default_factory=utc_now_iso)
    plots: list[PlotSpec] = Field(min_length=1)
