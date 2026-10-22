"""Plot tab renderer: build one plot, see it, save it into a dashboard."""

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from eyeboard.config import DEFAULT_SERIES_COLORS, PLOT_TYPES, THEMES
from eyeboard.dashboards.document import describe_validation_error
from eyeboard.dashboards.model import AGGREGATIONS, DASH_STYLES, PlotSpec, new_id
from eyeboard.plotting.figures import render_plot_from_spec
from eyeboard.plotting.specs import build_plot_spec_from_builder
from eyeboard.services.columns import normalize_colname
from eyeboard.services.dashboards import add_plot_to_dashboards
from eyeboard.state import remember_recent_dashboard
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.persistence import persist_dashboards_with_feedback
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown

LOGGER = logging.getLogger(__name__)

NEW_DASHBOARD = None  # the "Save into" choice that creates a dashboard


@dataclass(slots=True)
class PlotChoices:
    """What the controls of the Plot tab currently say."""

    data: pd.DataFrame
    x_col: str
    y_cols: list[str]
    plot_type: str
    enable_y2: bool = False
    y2_cols: list[str] = field(default_factory=list)
    color_col: str | None = None
    agg: str | None = None
    theme: str = "plotly_white"
    title: str = ""
    yaxis_title_1: str = ""
    yaxis_title_2: str = ""
    series_style: dict[str, dict[str, Any]] = field(default_factory=dict)


def render_plot_tab(dataset: MainDatasetContext) -> None:
    """Render the Plot tab: controls on the left, figure and saving on the right."""
    controls, result = st.columns([1, 2], gap="large")
    with controls:
        choices = render_controls(dataset)
    with result:
        spec = render_preview(choices)
        st.divider()
        render_save_section(spec)


def render_controls(dataset: MainDatasetContext) -> PlotChoices:
    """Render the data, axes, type and style controls."""
    st.markdown("##### Data and axes")
    data = render_date_filter(dataset)

    x_default = (
        dataset.date_col if dataset.date_col in dataset.cols else dataset.cols[0]
    )
    x_col = st.selectbox(
        "X axis", options=dataset.cols, index=dataset.cols.index(x_default)
    )
    numeric = [
        col
        for col in dataset.cols
        if pd.api.types.is_numeric_dtype(dataset.df_parsed[col])
    ]
    y_cols = st.multiselect(
        "Y axis (primary)",
        options=dataset.cols,
        default=(numeric or dataset.cols)[:1],
    )
    plot_type = st.radio("Type", options=PLOT_TYPES, horizontal=True, index=0)

    enable_y2 = st.toggle("Secondary Y axis", value=False)
    y2_cols: list[str] = []
    if enable_y2:
        y2_cols = st.multiselect(
            "Y axis (secondary)",
            options=[col for col in dataset.cols if col not in y_cols],
        )
    color_col = st.selectbox("Color/group by (optional)", [None, *dataset.cols])
    with st.expander("Aggregation (for a categorical X)"):
        agg = st.selectbox("Aggregate Y by X", [None, *AGGREGATIONS])
        st.caption("Useful when X is categorical with many rows per category.")

    with st.expander("Titles and theme"):
        theme = st.selectbox("Theme", THEMES, index=THEMES.index("plotly_white"))
        title = st.text_input("Plot title (optional)")
        yaxis_title_1 = st.text_input("Y1 axis title (optional)")
        yaxis_title_2 = st.text_input("Y2 axis title (optional)") if enable_y2 else ""

    series_style = render_series_styling(y_cols, y2_cols)
    return PlotChoices(
        data=data,
        x_col=x_col,
        y_cols=y_cols,
        plot_type=plot_type,
        enable_y2=enable_y2,
        y2_cols=y2_cols,
        color_col=color_col,
        agg=agg,
        theme=theme,
        title=title,
        yaxis_title_1=yaxis_title_1,
        yaxis_title_2=yaxis_title_2,
        series_style=series_style,
    )


def render_date_filter(dataset: MainDatasetContext) -> pd.DataFrame:
    """Offer a date range slider and return the rows inside it."""
    date_col = dataset.date_col
    if not date_col or date_col not in dataset.df_parsed.columns:
        return dataset.df_parsed
    dates = dataset.df_parsed[date_col]
    if not pd.api.types.is_datetime64_any_dtype(dates) or dates.notna().sum() == 0:
        return dataset.df_parsed

    first, last = dates.min().to_pydatetime(), dates.max().to_pydatetime()
    start, end = st.slider(
        "Date range", min_value=first, max_value=last, value=(first, last)
    )
    inside = dataset.df_parsed[(dates >= start) & (dates <= end)]
    if inside.empty:
        st.warning("The date range leaves no rows to plot.")
    return inside


def render_series_styling(
    y_cols: list[str], y2_cols: list[str]
) -> dict[str, dict[str, Any]]:
    """Render per-series colour, width and dash; return them only when customised.

    The widgets always exist, so switching "Customise" off and on again does not
    lose what was set; only a switched-on customisation is saved with the plot.
    """
    series_list = list(dict.fromkeys([*y_cols, *y2_cols]))
    with st.expander("Series colours and lines"):
        customise = st.toggle(
            "Customise series",
            value=False,
            help="Off: the theme's colours are used and nothing is saved with the plot.",
        )
        if not series_list:
            st.info("Select Y columns to customise them.")
        style_map: dict[str, dict[str, Any]] = {}
        for idx, series_name in enumerate(series_list):
            safe = normalize_colname(series_name).replace(" ", "_") or "series"
            color_key = f"sty_{safe}_color"
            if color_key not in st.session_state:
                st.session_state[color_key] = DEFAULT_SERIES_COLORS[
                    idx % len(DEFAULT_SERIES_COLORS)
                ]
            st.markdown(f"**{escape_markdown(series_name)}**")
            c1, c2, c3 = st.columns([1.2, 1, 1])
            color = c1.color_picker(
                "Color",
                key=color_key,
                label_visibility="collapsed",
                disabled=not customise,
            )
            width = c2.slider(
                "Width",
                1,
                8,
                2,
                key=f"sty_{safe}_width",
                label_visibility="collapsed",
                disabled=not customise,
            )
            dash = c3.selectbox(
                "Style",
                DASH_STYLES,
                key=f"sty_{safe}_dash",
                label_visibility="collapsed",
                disabled=not customise,
            )
            style_map[series_name] = {"color": color, "width": width, "dash": dash}
    return style_map if customise else {}


def build_spec(choices: PlotChoices) -> tuple[PlotSpec | None, list[str]]:
    """Turn the controls into a valid plot, or say why that is not possible."""
    try:
        spec = build_plot_spec_from_builder(
            title=choices.title.strip() or None,
            x_col=choices.x_col,
            y_cols=choices.y_cols,
            plot_type=choices.plot_type,
            theme=choices.theme,
            enable_secondary_axis=choices.enable_y2,
            y2_cols=choices.y2_cols,
            yaxis_title_1=choices.yaxis_title_1.strip() or None,
            yaxis_title_2=choices.yaxis_title_2.strip() or None,
            color_col=choices.color_col,
            agg=choices.agg,
            series_style=choices.series_style,
        )
    except ValidationError as exc:
        return None, describe_validation_error(exc)
    return spec, []


def render_preview(choices: PlotChoices) -> PlotSpec | None:
    """Draw the figure of the current choices; return the spec when it was drawn."""
    if not choices.y_cols and not choices.y2_cols:
        st.info("Pick an X column and at least one Y column.")
        return None

    spec, problems = build_spec(choices)
    if spec is None:
        for line in problems:
            st.warning(escape_markdown(line))
        return None

    try:
        fig, warnings = render_plot_from_spec(
            choices.data, spec, list(choices.data.columns)
        )
    except Exception as exc:  # UI boundary: show the problem, keep the traceback
        LOGGER.exception("Plot generation failed.")
        st.error(f"Error generating plot: {exc}")
        return None

    if warnings:
        with st.expander("Warnings"):
            for warning in warnings:
                (st.info if warning.startswith("Matched ") else st.warning)(warning)
    if fig is None:
        return None
    st.plotly_chart(fig, width="stretch", key="plot_preview")
    return spec


def render_save_section(spec: PlotSpec | None) -> None:
    """Choose a dashboard (or a new one) and save the plot into it."""
    st.markdown("##### Save to dashboard")
    by_id = {d.id: d for d in sorted(state.dashboards, key=lambda d: d.name.lower())}
    options = [NEW_DASHBOARD, *by_id]
    # Right after a save the new dashboard is the natural target of the next one.
    index = (
        options.index(state.plot_save_target)
        if state.plot_save_target in options
        else 0
    )
    target = st.selectbox(
        "Save into",
        options,
        index=index,
        format_func=lambda value: (
            "New dashboard" if value is NEW_DASHBOARD else by_id[value].name
        ),
    )
    if target is NEW_DASHBOARD:
        name = st.text_input(
            "Dashboard name",
            placeholder="e.g. Discharge dashboard",
            help="A name that already exists adds the plot to that dashboard.",
        )
    else:
        name = by_id[target].name
    label = st.text_input("Plot label (optional)", placeholder="e.g. Q (m3/s) vs time")

    disabled = spec is None or not name.strip()
    if st.button("Save to dashboard", width="stretch", disabled=disabled):
        save_plot(spec, name.strip(), label.strip())


def save_plot(spec: PlotSpec | None, name: str, label: str) -> None:
    """Add the plot to the named dashboard and save the dashboards."""
    if spec is None:
        return
    plot = spec.model_copy(update={"id": new_id(), "title": label or spec.title})
    dashboards, target, created = add_plot_to_dashboards(state.dashboards, name, plot)
    if not persist_dashboards_with_feedback(dashboards):
        return
    state.active_dashboard_id = target.id
    state.plot_save_target = target.id
    remember_recent_dashboard(state, target.id)
    st.toast(
        f"Dashboard '{target.name}' created."
        if created
        else f"Plot added to '{target.name}'."
    )
    st.rerun()
