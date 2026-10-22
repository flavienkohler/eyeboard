"""Streamlit application composition for EyeBoard."""

import pandas as pd
import streamlit as st

from eyeboard.config import APP_LAYOUT, APP_PAGE_ICON, APP_PAGE_TITLE
from eyeboard.dashboards.document import LoadResult
from eyeboard.models import CsvReadReport, DateSettings, ReadOptions
from eyeboard.paths import data_dir
from eyeboard.services.columns import guess_date_column
from eyeboard.services.dataset import DataSource, source_from_upload
from eyeboard.services.legacy import LegacyImport
from eyeboard.services.recent_csvs import (
    remember_recent_csv,
)
from eyeboard.state import initialize_state
from eyeboard.ui.cache import (
    load_table_cached,
    parse_table_cached,
    profile_table_cached,
)
from eyeboard.ui.context import MainDatasetContext, SidebarSelection
from eyeboard.ui.header import render_dataset_summary, render_header
from eyeboard.ui.session import state
from eyeboard.ui.sidebar import (
    render_date_options,
    render_sidebar,
    render_status_card,
    upload_signature,
)
from eyeboard.ui.source_picker import source_for_recent
from eyeboard.ui.tabs.compare import render_compare_tab
from eyeboard.ui.tabs.dashboards import render_dashboards_tab
from eyeboard.ui.tabs.explore import render_explore_tab
from eyeboard.ui.tabs.plot import render_plot_tab
from eyeboard.ui.text import escape_markdown


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(
        page_title=APP_PAGE_TITLE,
        page_icon=APP_PAGE_ICON,
        layout=APP_LAYOUT,
    )

    initialize_state(state)
    render_header()

    render_legacy_import_notice(state.legacy_import)
    render_dashboards_load_problems(state.dashboards_loaded)

    sidebar_selection = render_sidebar()
    read_options = sidebar_selection.read_options

    source = resolve_source(sidebar_selection)
    if source is None:
        st.info("Upload a CSV to start.")
        st.stop()

    df, read_report, error = load_table_cached(source, read_options)
    if error:
        st.error(f"Could not read CSV: {error}")
        st.stop()
    remember_source(sidebar_selection, source)

    date_settings = render_date_options(list(df.columns), source.key)
    dataset = build_main_dataset_context(
        df, read_report, source, read_options, date_settings
    )
    with sidebar_selection.status_slot:
        render_status_card(dataset)
    render_dataset_summary(dataset)

    tabs = st.tabs(
        [
            "Explore",
            "Plot",
            "Dashboards",
            "Compare",
        ]
    )

    with tabs[0]:
        render_explore_tab(dataset)
    with tabs[1]:
        render_plot_tab(dataset)
    with tabs[2]:
        render_dashboards_tab(dataset)
    with tabs[3]:
        render_compare_tab(dataset)


def render_legacy_import_notice(imported: LegacyImport) -> None:
    """Say once that files of an older version were copied to the data folder."""
    if not imported.happened:
        return
    copied = []
    if imported.dashboards_from is not None:
        copied.append(f"your dashboards (from `{imported.dashboards_from}`)")
    if imported.recent_files:
        copied.append(
            f"{imported.recent_files} recent file(s) (from `{imported.recent_from}`)"
        )
    st.info(
        f"EyeBoard now keeps its files in `{data_dir()}`. Copied: "
        + " and ".join(copied)
        + ". The old files are no longer used and can be deleted."
    )


def render_dashboards_load_problems(loaded: LoadResult) -> None:
    """Tell the user about saved dashboards that could not be loaded."""
    if not loaded.problems:
        return
    with st.container(border=True):
        show = st.error if loaded.blocked else st.warning
        show("Some saved dashboards could not be loaded.")
        for problem in loaded.problems:
            st.caption(escape_markdown(problem))


def resolve_source(selection: SidebarSelection) -> DataSource | None:
    """Turn the sidebar choice (recent file or upload) into a data source."""
    if selection.recent_csv_id is not None:
        source = source_for_recent(selection.recent_csv_id)
        if source is not None:
            return source
        st.warning("The selected recent file is no longer available.")
    if selection.uploaded_file is not None:
        return source_from_upload(selection.uploaded_file)
    return None


def remember_source(selection: SidebarSelection, source: DataSource) -> None:
    """Record the loaded file in the recent list, once per new upload."""
    if selection.recent_csv_id is not None:
        state.active_recent_csv_id = selection.recent_csv_id
        state.active_csv_source = "recent"
        return

    uploaded = selection.uploaded_file
    if uploaded is None or state.remembered_upload_key == source.key:
        return
    entry = remember_recent_csv(uploaded.name, uploaded.getvalue())
    state.remembered_upload_key = source.key
    state.active_recent_csv_id = entry.get("id")
    state.active_csv_source = "upload"
    state.last_uploaded_csv_signature = upload_signature(uploaded)


def build_main_dataset_context(
    df: pd.DataFrame,
    read_report: CsvReadReport,
    source: DataSource,
    read_options: ReadOptions,
    date_settings: DateSettings,
) -> MainDatasetContext:
    """Build the derived dataset context shared across tabs."""
    parsed = parse_table_cached(source, read_options, date_settings, df)
    cols = list(df.columns)
    return MainDatasetContext(
        df=df,
        df_parsed=parsed.df,
        source=source,
        read_options=read_options,
        date_settings=date_settings,
        cols=cols,
        date_col=date_settings.column,
        date_guess=guess_date_column(cols),
        label=source.label,
        read_report=read_report,
        date_parse_success_count=parsed.date_parse_success_count,
        date_parse_candidate_count=parsed.date_parse_candidate_count,
        date_parse_mode=date_settings.mode,
        date_format=date_settings.format,
        date_parse_warning=parsed.date_parse_warning,
        date_order=parsed.date_order,
        profiles=profile_table_cached(source, read_options, date_settings, parsed.df),
    )
