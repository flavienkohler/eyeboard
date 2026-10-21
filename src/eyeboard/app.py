"""Streamlit application composition for EyeBoard."""

import pandas as pd
import streamlit as st

from eyeboard.config import APP_LAYOUT, APP_PAGE_ICON, APP_PAGE_TITLE
from eyeboard.dashboards.document import LoadResult
from eyeboard.services.columns import guess_date_column
from eyeboard.services.csv_reading import read_csv_input
from eyeboard.services.date_parsing import parse_dates_flexible
from eyeboard.services.recent_csvs import (
    get_recent_csv_cache_path,
    get_recent_csv_entry,
    remember_recent_csv,
    touch_recent_csv,
)
from eyeboard.state import initialize_session_state
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.header import render_dataset_summary, render_header
from eyeboard.ui.sidebar import render_sidebar
from eyeboard.ui.tabs.compare import render_compare_tab
from eyeboard.ui.tabs.dashboard import render_dashboard_tab
from eyeboard.ui.tabs.dashboards_manager import render_dashboards_manager_tab
from eyeboard.ui.tabs.plot_builder import render_plot_builder_tab
from eyeboard.ui.tabs.preview import render_preview_tab
from eyeboard.ui.text import escape_markdown


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(
        page_title=APP_PAGE_TITLE,
        page_icon=APP_PAGE_ICON,
        layout=APP_LAYOUT,
    )

    initialize_session_state(st.session_state)
    render_header()

    render_dashboards_load_problems(st.session_state["dashboards_loaded"])

    sidebar_selection = render_sidebar()
    csv_path = ""
    uploaded_file = sidebar_selection.uploaded_file
    path_source_kind = "Server path"
    recent_csv_entry = None
    if sidebar_selection.recent_csv_id is not None:
        csv_path = str(get_recent_csv_cache_path(sidebar_selection.recent_csv_id))
        recent_csv_entry = get_recent_csv_entry(sidebar_selection.recent_csv_id)
        uploaded_file = None
        path_source_kind = "Recent cache"

    df, label, err, read_report = read_csv_input(
        uploaded_file,
        csv_path,
        decimal=sidebar_selection.reading_options.decimal,
        sep=sidebar_selection.reading_options.sep,
        header=sidebar_selection.reading_options.header,
        skiprows=sidebar_selection.reading_options.skiprows,
        encoding=sidebar_selection.reading_options.encoding,
        path_source_kind=path_source_kind,
    )

    if err:
        st.session_state["df"] = None
        st.session_state["file_label"] = ""
        st.session_state["read_report"] = None
        st.error(f"Could not read CSV: {err}")
    elif df is not None:
        if recent_csv_entry is not None:
            label = recent_csv_entry.get("filename", label)
            if read_report is not None:
                read_report.source_label = label
        st.session_state["df"] = df
        st.session_state["file_label"] = label
        st.session_state["read_report"] = read_report
        if sidebar_selection.recent_csv_id is not None:
            touch_recent_csv(sidebar_selection.recent_csv_id)
            st.session_state["active_recent_csv_id"] = sidebar_selection.recent_csv_id
            st.session_state["active_csv_source"] = "recent"
        elif sidebar_selection.uploaded_file is not None:
            recent_entry = remember_recent_csv(
                sidebar_selection.uploaded_file.name,
                sidebar_selection.uploaded_file.getvalue(),
            )
            st.session_state["active_recent_csv_id"] = recent_entry.get("id")
            st.session_state["active_csv_source"] = "upload"
            st.session_state["last_uploaded_csv_signature"] = (
                f"{sidebar_selection.uploaded_file.name}:"
                f"{len(sidebar_selection.uploaded_file.getvalue())}"
            )

    current_df = st.session_state["df"]
    if current_df is None:
        st.info("Upload a CSV to start.")
        st.stop()

    dataset = build_main_dataset_context(current_df)
    render_dataset_summary(dataset)

    tabs = st.tabs(
        [
            "Preview",
            "Plot Builder",
            "Dashboard",
            "Compare (2 CSVs)",
            "Dashboards Manager",
        ]
    )

    with tabs[0]:
        render_preview_tab(dataset)
    with tabs[1]:
        render_plot_builder_tab(dataset)
    with tabs[2]:
        render_dashboard_tab(dataset)
    with tabs[3]:
        render_compare_tab(dataset, sidebar_selection.reading_options)
    with tabs[4]:
        render_dashboards_manager_tab(dataset)


def render_dashboards_load_problems(loaded: LoadResult) -> None:
    """Tell the user about saved dashboards that could not be loaded."""
    if not loaded.problems:
        return
    with st.container(border=True):
        show = st.error if loaded.blocked else st.warning
        show("Some saved dashboards could not be loaded.")
        for problem in loaded.problems:
            st.caption(escape_markdown(problem))


def build_main_dataset_context(df) -> MainDatasetContext:
    """Build the derived dataset context shared across tabs."""
    cols = list(df.columns)
    date_guess = guess_date_column(cols)
    date_mode = st.session_state.get("read_date_mode", "Auto-detect")
    date_format = (st.session_state.get("read_date_format", "") or "").strip() or None
    date_col_state = st.session_state.get("read_date_col")
    date_col = (
        date_col_state
        if date_col_state in cols
        else (date_guess if date_guess in cols else None)
    )
    df_parsed = parse_dates_flexible(
        df,
        date_col,
        date_mode=date_mode,
        date_format=date_format,
    )
    date_parse_success_count, date_parse_candidate_count, date_parse_warning = (
        build_date_parse_summary(df, df_parsed, date_col)
    )
    return MainDatasetContext(
        df=df,
        df_parsed=df_parsed,
        cols=cols,
        date_col=date_col,
        date_guess=date_guess,
        label=st.session_state["file_label"] or "CSV",
        read_report=st.session_state.get("read_report"),
        date_parse_success_count=date_parse_success_count,
        date_parse_candidate_count=date_parse_candidate_count,
        date_parse_mode=date_mode,
        date_format=date_format,
        date_parse_warning=date_parse_warning,
    )


def build_date_parse_summary(
    df: pd.DataFrame,
    df_parsed: pd.DataFrame,
    date_col: str | None,
) -> tuple[int, int, str | None]:
    """Summarize how successfully the selected date column parsed."""
    if (
        date_col is None
        or date_col not in df.columns
        or date_col not in df_parsed.columns
    ):
        return 0, 0, None

    source_series = df[date_col]
    parsed_series = df_parsed[date_col]
    candidate_mask = source_series.notna()

    if pd.api.types.is_object_dtype(source_series) or pd.api.types.is_string_dtype(
        source_series
    ):
        stripped = source_series.astype("string").str.strip()
        candidate_mask = candidate_mask & stripped.ne("")

    candidate_count = int(candidate_mask.sum())
    success_count = int(parsed_series[candidate_mask].notna().sum())
    if candidate_count == 0:
        return success_count, candidate_count, None

    success_rate = success_count / candidate_count
    warning = None
    if success_rate < 0.8:
        warning = (
            f"Only {success_count:,} of {candidate_count:,} non-empty date values "
            "parsed successfully."
        )
    return success_count, candidate_count, warning
