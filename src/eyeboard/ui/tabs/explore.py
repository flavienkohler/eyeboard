"""Explore tab renderer: how the file was read, what each column holds, quick plots."""

import math

import pandas as pd
import streamlit as st

from eyeboard.i18n import t
from eyeboard.plotting.figures import (
    COLUMN_PREVIEW_MAX_POINTS,
    make_column_preview_figure,
)
from eyeboard.services.columns import normalize_colname
from eyeboard.services.profile import profiles_to_frame
from eyeboard.ui.context import MainDatasetContext, dataset_fingerprint
from eyeboard.ui.header import render_read_report
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown

MINI_PLOT_AUTO_RENDER_MAX_ROWS = 5_000
MINI_PLOT_AUTO_RENDER_MAX_COLUMNS = 24
MINI_PLOT_PAGE_SIZES = (9, 18, 30)
PREVIEW_ROWS = 200
TABLE_MAX_HEIGHT = 420


def _reset_for_new_dataset(dataset: MainDatasetContext) -> None:
    """Start the mini-plot paging again, and pause plots for big files."""
    signature = dataset_fingerprint(dataset)
    if state.explore_signature == signature:
        return
    state.explore_signature = signature
    state.explore_mini_plots = (
        len(dataset.df) <= MINI_PLOT_AUTO_RENDER_MAX_ROWS
        and len(dataset.cols) <= MINI_PLOT_AUTO_RENDER_MAX_COLUMNS
    )
    state.explore_page = 1
    state.explore_show_rows = False


def _prepare_preview_x(
    dataset: MainDatasetContext,
) -> tuple[str | None, pd.Series | None]:
    """Pre-sort the shared preview x-axis once so each mini-plot can reuse it."""
    preview_x_col = dataset.date_col if dataset.date_col in dataset.cols else None
    if not preview_x_col:
        return None, None

    parsed_x = dataset.df_parsed[preview_x_col]
    if (
        not pd.api.types.is_datetime64_any_dtype(parsed_x)
        or parsed_x.notna().sum() == 0
    ):
        return None, None

    return preview_x_col, parsed_x.dropna().sort_values(kind="stable")


def render_explore_tab(dataset: MainDatasetContext) -> None:
    """Render the explore tab."""
    render_read_report(dataset)
    render_decimal_warning(dataset)

    st.text_input(
        t("Search columns"),
        key="explore_filter",
        placeholder=t("Type part of a column name"),
        help=t("Filters the table and the plots below."),
    )
    needle = normalize_colname(state.explore_filter)
    matching = [col for col in dataset.cols if needle in normalize_colname(col)]

    render_columns_table(dataset, matching)

    if st.toggle(
        t("Show the first {count} rows", count=PREVIEW_ROWS),
        key="explore_show_rows",
    ):
        st.dataframe(dataset.df.head(PREVIEW_ROWS), width="stretch", height=420)

    st.markdown(t("##### Column plots"))
    render_mini_plots(dataset, matching)


def render_decimal_warning(dataset: MainDatasetContext) -> None:
    """Warn when numbers look written with a decimal comma but are read as text."""
    names = [p.name for p in dataset.profiles if p.decimal_comma]
    if not names:
        return
    shown = ", ".join(f"`{escape_markdown(name)}`" for name in names[:5])
    more = t(" and {count} more", count=len(names) - 5) if len(names) > 5 else ""
    st.warning(
        t(
            "{count} column(s) look like numbers with a decimal comma but are read as text: {shown}{more}. Set **Decimal** to *Comma (,)* in Reading options.",
            count=len(names),
            shown=shown,
            more=more,
        )
    )


def render_columns_table(dataset: MainDatasetContext, matching: list[str]) -> None:
    """Show one row per column: type, gaps, distinct values, range and checks."""
    wanted = set(matching)
    frame = profiles_to_frame([p for p in dataset.profiles if p.name in wanted])
    frame["type"] = frame["type"].map(t)
    frame = frame.rename(columns=t)
    if frame.empty:
        st.info(t("No column matches the search."))
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        height=min(TABLE_MAX_HEIGHT, 38 + 35 * len(frame)),
        column_config={
            t("missing %"): st.column_config.NumberColumn(format="%.1f"),
            t("distinct"): st.column_config.NumberColumn(
                help=t("Exact number of different values (no rounding).")
            ),
        },
    )


def render_mini_plots(dataset: MainDatasetContext, matching: list[str]) -> None:
    """Show a small plot per column, one page at a time."""
    preview_x_col, preview_x_series = _prepare_preview_x(dataset)
    plot_cols = [col for col in matching if col != preview_x_col]
    if preview_x_col:
        st.caption(
            t(
                "Non-time columns, with `{preview_x_col}` as the shared x-axis.",
                preview_x_col=preview_x_col,
            )
        )
    if not plot_cols:
        st.info(t("No column to plot."))
        return

    controls = st.columns([1.2, 0.9, 0.8], vertical_alignment="bottom")
    with controls[0]:
        draw = st.toggle(
            t("Draw the plots of this page"),
            key="explore_mini_plots",
            help=t("Paused by default for large files so the tab stays responsive."),
        )
    with controls[1]:
        page_size = st.selectbox(
            t("Plots per page"), list(MINI_PLOT_PAGE_SIZES), key="explore_page_size"
        )
    total_pages = max(1, math.ceil(len(plot_cols) / page_size))
    state.explore_page = min(state.explore_page, total_pages)
    with controls[2]:
        st.number_input(
            t("Page"), min_value=1, max_value=total_pages, step=1, key="explore_page"
        )

    start_idx = (state.explore_page - 1) * page_size
    visible = plot_cols[start_idx : start_idx + page_size]
    st.caption(
        t(
            "Showing columns {first}-{last} of {count}. Numeric plots are capped at {limit} points.",
            first=start_idx + 1,
            last=start_idx + len(visible),
            count=len(plot_cols),
            limit=COLUMN_PREVIEW_MAX_POINTS,
        )
    )
    if not draw:
        st.info(t("Plots are paused. Switch on the toggle above to draw this page."))
        return

    for start in range(0, len(visible), 3):
        row_cols = st.columns(3)
        for offset, col in enumerate(visible[start : start + 3]):
            with row_cols[offset]:
                st.markdown(f"**{escape_markdown(col)}**")
                mini_fig = make_column_preview_figure(
                    dataset.df[col],
                    x_series=preview_x_series,
                    x_label=preview_x_col,
                    x_sorted=preview_x_series is not None,
                )
                if mini_fig is None:
                    st.caption(t("No plot available."))
                    continue
                st.plotly_chart(
                    mini_fig,
                    width="stretch",
                    key=f"explore_mini_{start_idx + start + offset}_{normalize_colname(col)}",
                )
