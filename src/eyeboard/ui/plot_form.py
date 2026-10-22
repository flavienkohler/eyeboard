"""The plot form: one set of controls for drawing a new plot or editing a saved one.

``render_plot_form`` is given the plot to start from (or none) and a key prefix.
Every widget has a key built from the prefix, so two forms (a new plot and an
edited one) never share state, and the prefix changes with the loaded file, so
choices that no longer exist in the new columns do not linger.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from eyeboard.config import DEFAULT_SERIES_COLORS, PLOT_TYPES, THEMES
from eyeboard.dashboards.document import describe_validation_error
from eyeboard.dashboards.model import AGGREGATIONS, DASH_STYLES, PlotSpec, SeriesStyle
from eyeboard.i18n import t
from eyeboard.plotting.export import png_config
from eyeboard.plotting.figures import is_info_note, render_plot_from_spec
from eyeboard.plotting.specs import build_plot_spec_from_builder
from eyeboard.services.columns import normalize_colname
from eyeboard.services.profile import suggested_series
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.exports import render_downloads
from eyeboard.ui.text import escape_markdown

LOGGER = logging.getLogger(__name__)

DEFAULT_THEME = "plotly_white"


@dataclass(slots=True)
class PlotChoices:
    """What the controls of the plot form currently say."""

    data: pd.DataFrame
    x_col: str
    y_cols: list[str]
    plot_type: str
    enable_y2: bool = False
    y2_cols: list[str] = field(default_factory=list)
    color_col: str | None = None
    agg: str | None = None
    theme: str = DEFAULT_THEME
    title: str = ""
    yaxis_title_1: str = ""
    yaxis_title_2: str = ""
    series_style: dict[str, dict[str, Any]] = field(default_factory=dict)


def _keep(columns: list[str], available: list[str]) -> list[str]:
    """The requested columns that exist in this file."""
    return [col for col in columns if col in available]


def render_plot_form(
    dataset: MainDatasetContext,
    *,
    initial: PlotSpec | None,
    key_prefix: str,
    date_filter: bool,
) -> PlotChoices:
    """Render the data, axes, type and style controls, filled from ``initial``."""
    cols = dataset.cols
    start = initial or PlotSpec(x_col="x", y_cols=["y"])  # only its defaults are used

    def key(name: str) -> str:
        return f"{key_prefix}_{name}"

    st.markdown(t("##### Data and axes"))
    data = (
        render_date_filter(dataset, key("dates")) if date_filter else dataset.df_parsed
    )

    x_default = start.x_col if initial and start.x_col in cols else None
    if x_default is None:
        x_default = dataset.date_col if dataset.date_col in cols else cols[0]
    x_col = st.selectbox(
        t("X axis"), options=cols, index=cols.index(x_default), key=key("x")
    )

    if initial:
        y_default = _keep(start.y_cols, cols)
    else:
        y_default = _keep(suggested_series(dataset.profiles), cols) or cols[:1]
    y_cols = st.multiselect(
        t("Y axis (primary)"), options=cols, default=y_default, key=key("y")
    )
    plot_type = st.radio(
        t("Type"),
        options=PLOT_TYPES,
        format_func=t,
        horizontal=True,
        index=PLOT_TYPES.index(start.plot_type),
        key=key("type"),
    )

    y2_default = [col for col in _keep(start.y2_cols, cols) if col not in y_cols]
    enable_y2 = st.toggle(
        t("Secondary Y axis"), value=bool(y2_default), key=key("enable_y2")
    )
    y2_cols: list[str] = []
    if enable_y2:
        y2_cols = st.multiselect(
            t("Y axis (secondary)"),
            options=[col for col in cols if col not in y_cols],
            default=y2_default,
            key=key("y2"),
        )
    color_options = [None, *cols]
    color_col = st.selectbox(
        t("Color/group by (optional)"),
        color_options,
        index=color_options.index(start.color_col)
        if start.color_col in color_options
        else 0,
        key=key("color"),
    )
    with st.expander(t("Aggregation (for a categorical X)")):
        agg_options = [None, *AGGREGATIONS]
        agg = st.selectbox(
            t("Aggregate Y by X"),
            agg_options,
            format_func=lambda value: t("none") if value is None else t(value),
            index=agg_options.index(start.agg),
            key=key("agg"),
        )
        st.caption(t("Useful when X is categorical with many rows per category."))

    with st.expander(t("Titles and theme")):
        theme = st.selectbox(
            t("Theme"),
            THEMES,
            index=THEMES.index(start.theme if initial else DEFAULT_THEME),
            key=key("theme"),
        )
        title = st.text_input(
            t("Plot title (optional)"), value=start.title or "", key=key("title")
        )
        yaxis_title_1 = st.text_input(
            t("Y1 axis title (optional)"),
            value=start.yaxis_title_1 or "",
            key=key("ytitle1"),
        )
        yaxis_title_2 = (
            st.text_input(
                t("Y2 axis title (optional)"),
                value=start.yaxis_title_2 or "",
                key=key("ytitle2"),
            )
            if enable_y2
            else ""
        )

    series_style = render_series_styling(y_cols, y2_cols, start, key_prefix)
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


def render_date_filter(dataset: MainDatasetContext, key: str) -> pd.DataFrame:
    """Offer a date range slider and return the rows inside it."""
    date_col = dataset.date_col
    if not date_col or date_col not in dataset.df_parsed.columns:
        return dataset.df_parsed
    dates = dataset.df_parsed[date_col]
    if not pd.api.types.is_datetime64_any_dtype(dates) or dates.notna().sum() == 0:
        return dataset.df_parsed

    first, last = dates.min().to_pydatetime(), dates.max().to_pydatetime()
    start, end = st.slider(
        t("Date range"), min_value=first, max_value=last, value=(first, last), key=key
    )
    inside = dataset.df_parsed[(dates >= start) & (dates <= end)]
    if inside.empty:
        st.warning(t("The date range leaves no rows to plot."))
    return inside


def render_series_styling(
    y_cols: list[str], y2_cols: list[str], start: PlotSpec, key_prefix: str
) -> dict[str, dict[str, Any]]:
    """Render per-series color, width and dash; return them only when customized.

    The widgets always exist, so switching "Customize" off and on again does not
    lose what was set; only a switched-on customisation is saved with the plot.
    """
    series_list = list(dict.fromkeys([*y_cols, *y2_cols]))
    with st.expander(t("Series colors and lines"), expanded=bool(start.series_style)):
        customize = st.toggle(
            t("Customize series"),
            value=bool(start.series_style),
            key=f"{key_prefix}_customize",
            help=t(
                "Off: the theme's colors are used and nothing is saved with the plot."
            ),
        )
        if not series_list:
            st.info(t("Select Y columns to customize them."))
        style_map: dict[str, dict[str, Any]] = {}
        for idx, series_name in enumerate(series_list):
            saved = start.series_style.get(series_name) or SeriesStyle()
            safe = normalize_colname(series_name).replace(" ", "_") or "series"
            prefix = f"{key_prefix}_sty_{safe}"
            st.markdown(f"**{escape_markdown(series_name)}**")
            c1, c2, c3 = st.columns([1.2, 1, 1])
            color = c1.color_picker(
                t("Color"),
                value=saved.color
                or DEFAULT_SERIES_COLORS[idx % len(DEFAULT_SERIES_COLORS)],
                key=f"{prefix}_color",
                label_visibility="collapsed",
                disabled=not customize,
            )
            width = c2.slider(
                t("Width"),
                1,
                8,
                int(saved.width or 2),
                key=f"{prefix}_width",
                label_visibility="collapsed",
                disabled=not customize,
            )
            dash = c3.selectbox(
                t("Style"),
                DASH_STYLES,
                format_func=t,
                index=DASH_STYLES.index(saved.dash or "solid"),
                key=f"{prefix}_dash",
                label_visibility="collapsed",
                disabled=not customize,
            )
            style_map[series_name] = {"color": color, "width": width, "dash": dash}
    return style_map if customize else {}


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


def render_preview(
    choices: PlotChoices, chart_key: str, export_key: str | None = None
) -> PlotSpec | None:
    """Draw the figure of the current choices; return the spec when it was drawn.

    With ``export_key``, download buttons for the chart and its data follow it.
    """
    if not choices.y_cols and not choices.y2_cols:
        st.info(t("Pick an X column and at least one Y column."))
        return None

    spec, problems = build_spec(choices)
    if spec is None:
        st.error(t("These settings do not make a valid plot."))
        for line in problems:
            st.warning(escape_markdown(line))
        return None

    try:
        fig, warnings = render_plot_from_spec(
            choices.data, spec, list(choices.data.columns)
        )
    except Exception as exc:  # UI boundary: show the problem, keep the traceback
        LOGGER.exception("Plot generation failed.")
        st.error(t("Error generating plot: {exc}", exc=exc))
        return None

    if warnings:
        with st.expander(t("Warnings")):
            for warning in warnings:
                (st.info if is_info_note(warning) else st.warning)(warning)
    if fig is None:
        return None
    name = spec.title or "plot"
    st.plotly_chart(fig, width="stretch", key=chart_key, config=png_config(name))
    if export_key:
        used = [spec.x_col, *spec.y_cols, *spec.y2_cols, spec.color_col]
        columns = [c for c in dict.fromkeys(used) if c and c in choices.data.columns]
        render_downloads(
            toggle_key=export_key,
            name=name,
            fig=fig,
            table=choices.data[columns],
            table_label=t("Plotted data (CSV)"),
        )
    return spec
