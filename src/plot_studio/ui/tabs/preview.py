"""Preview tab renderer."""

import math

import pandas as pd
import streamlit as st

from plot_studio.plotting.figures import (
    COLUMN_PREVIEW_MAX_POINTS,
    make_column_preview_figure,
)
from plot_studio.services.columns import normalize_colname
from plot_studio.ui.header import render_read_report
from plot_studio.ui.context import MainDatasetContext

MINI_PLOT_AUTO_RENDER_MAX_ROWS = 5_000
MINI_PLOT_AUTO_RENDER_MAX_COLUMNS = 24
MINI_PLOT_PAGE_SIZES = (9, 18, 30)


def _preview_dataset_signature(dataset: MainDatasetContext) -> tuple[object, ...]:
    """Build a lightweight signature so preview state resets on new datasets."""
    return (
        len(dataset.df),
        len(dataset.cols),
        dataset.date_col,
        tuple(str(col) for col in dataset.cols[:12]),
    )


def _initialize_mini_plot_state(
    dataset: MainDatasetContext, preview_cols: list[str]
) -> None:
    """Initialize rendering state for the current dataset."""
    signature = _preview_dataset_signature(dataset)
    if st.session_state.get("preview_mini_plot_signature") == signature:
        return

    auto_render = (
        len(dataset.df) <= MINI_PLOT_AUTO_RENDER_MAX_ROWS
        and len(preview_cols) <= MINI_PLOT_AUTO_RENDER_MAX_COLUMNS
    )
    st.session_state["preview_mini_plot_signature"] = signature
    st.session_state["preview_render_mini_plots"] = auto_render
    st.session_state["preview_mini_plot_page"] = 1


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


def render_preview_tab(dataset: MainDatasetContext) -> None:
    """Render the dataset preview tab."""
    render_read_report(dataset)

    c1, c2 = st.columns([1.1, 1], vertical_alignment="top")
    with c1:
        st.markdown("##### Quick preview")
        st.dataframe(dataset.df.head(200), width="stretch", height=420)
    with c2:
        st.markdown("##### Columns & types")
        info_df = pd.DataFrame(
            {
                "column": dataset.cols,
                "dtype": [str(dataset.df[col].dtype) for col in dataset.cols],
            }
        )
        st.dataframe(info_df, width="stretch", height=420)
    with st.expander("Show summary statistics", expanded=False):
        st.dataframe(dataset.df.describe(include="all").transpose(), width="stretch")

    with st.expander("Column mini plots (all columns)", expanded=False):
        preview_x_col, preview_x_series = _prepare_preview_x(dataset)

        mini_plot_cols = [col for col in dataset.cols if col != preview_x_col]
        if preview_x_col:
            st.caption(
                f"Quick scan of all non-time columns using `{preview_x_col}` as shared x-axis."
            )
        else:
            st.caption("Quick scan of all columns.")

        if not mini_plot_cols:
            st.info("No preview columns available.")
            return

        _initialize_mini_plot_state(dataset, mini_plot_cols)

        render_mini_plots = st.toggle(
            "Render mini plots for the current page",
            key="preview_render_mini_plots",
            help=(
                "Large datasets pause this by default so the preview tab stays "
                "responsive. Only the visible page is rendered."
            ),
        )

        controls = st.columns([1.4, 0.9, 0.8], vertical_alignment="bottom")
        with controls[0]:
            filter_text = st.text_input(
                "Filter columns",
                key="preview_mini_plot_filter",
                placeholder="Type part of a column name",
            )
        with controls[1]:
            page_size = st.selectbox(
                "Plots per page",
                options=list(MINI_PLOT_PAGE_SIZES),
                index=1,
                key="preview_mini_plot_page_size",
            )

        normalized_filter = normalize_colname(filter_text)
        filtered_cols = [
            col
            for col in mini_plot_cols
            if normalized_filter in normalize_colname(col)
        ]
        if not filtered_cols:
            st.info("No preview columns match the current filter.")
            return

        total_pages = max(1, math.ceil(len(filtered_cols) / page_size))
        if st.session_state.get("preview_mini_plot_page", 1) > total_pages:
            st.session_state["preview_mini_plot_page"] = total_pages

        with controls[2]:
            st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                step=1,
                key="preview_mini_plot_page",
            )

        page = int(st.session_state["preview_mini_plot_page"])
        start_idx = (page - 1) * page_size
        visible_cols = filtered_cols[start_idx : start_idx + page_size]
        end_idx = start_idx + len(visible_cols)

        st.caption(
            f"Showing columns {start_idx + 1}-{end_idx} of {len(filtered_cols)}. "
            f"Numeric previews are capped at {COLUMN_PREVIEW_MAX_POINTS} points."
        )

        if not render_mini_plots:
            st.info(
                "Mini-plot rendering is paused. Enable it above to load only the "
                "current page."
            )
            return

        for start in range(0, len(visible_cols), 3):
            row_cols = st.columns(3)
            for offset, col in enumerate(visible_cols[start : start + 3]):
                with row_cols[offset]:
                    st.markdown(f"**{col}**")
                    mini_fig = make_column_preview_figure(
                        dataset.df[col],
                        x_series=preview_x_series,
                        x_label=preview_x_col,
                        x_sorted=preview_x_series is not None,
                    )
                    if mini_fig is not None:
                        idx = start_idx + start + offset
                        st.plotly_chart(
                            mini_fig,
                            width="stretch",
                            key=f"preview_mini_{idx}_{normalize_colname(col)}",
                        )
                    else:
                        st.caption("No preview available.")
