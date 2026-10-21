"""Sidebar rendering for data selection and reading options."""

import streamlit as st

from eyeboard.config import DATE_PARSE_MODES, ENCODING_OPTIONS
from eyeboard.models import DateSettings, ReadOptions
from eyeboard.paths import recent_dir
from eyeboard.services.columns import guess_date_column
from eyeboard.services.recent_csvs import (
    clear_recent_csvs,
    format_recent_csv_details,
    list_recent_csvs,
    touch_recent_csv,
)
from eyeboard.ui.context import SidebarSelection
from eyeboard.ui.session import state


def render_sidebar() -> SidebarSelection:
    """Render the main sidebar and return the current selections."""
    with st.sidebar:
        uploaded_file, recent_csv_id = render_data_section()
        st.divider()
        read_options = render_reading_options()

    return SidebarSelection(
        uploaded_file=uploaded_file,
        recent_csv_id=recent_csv_id,
        read_options=read_options,
    )


def render_data_section():
    """Render the file-selection and active-dashboard section."""
    with st.expander("Data", expanded=True):
        uploaded_file = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            help="Upload a CSV file from your computer.",
        )
        selected_recent_csv_id = None
        uploaded_signature = None
        if uploaded_file is not None:
            uploaded_signature = upload_signature(uploaded_file)

        recent_csvs = list_recent_csvs()
        if recent_csvs:
            st.caption("Recent CSVs")
            top_recent_csvs = recent_csvs[:3]
            older_recent_csvs = recent_csvs[3:]

            for entry in top_recent_csvs:
                entry_id = entry.get("id")
                filename = entry.get("filename", "Unnamed CSV")
                if st.button(
                    filename,
                    key=f"recent_csv_{entry_id}",
                    width="stretch",
                    type=(
                        "primary"
                        if state.active_recent_csv_id == entry_id
                        and state.active_csv_source == "recent"
                        else "secondary"
                    ),
                ):
                    selected_recent_csv_id = entry_id
                    touch_recent_csv(entry_id)
                    state.active_recent_csv_id = entry_id
                    state.active_csv_source = "recent"
                    st.rerun()
                st.caption(format_recent_csv_details(entry))

            if older_recent_csvs:
                older_map = {
                    entry.get("id"): entry.get("filename", "Unnamed CSV")
                    for entry in older_recent_csvs
                    if entry.get("id")
                }
                older_options = list(older_map)
                selected_older_recent = st.selectbox(
                    "Older recent CSVs",
                    options=[None] + older_options,
                    index=0,
                    format_func=lambda value: (
                        "Choose an older recent CSV"
                        if value is None
                        else older_map.get(value, "Unnamed CSV")
                    ),
                    help="Scroll through older recently opened CSVs.",
                )
                if selected_older_recent is not None:
                    older_entry = next(
                        (
                            entry
                            for entry in older_recent_csvs
                            if entry.get("id") == selected_older_recent
                        ),
                        None,
                    )
                    if older_entry is not None:
                        st.caption(format_recent_csv_details(older_entry))
                    if st.button(
                        "Open selected recent CSV",
                        key="open_older_recent_csv",
                        width="stretch",
                    ):
                        selected_recent_csv_id = selected_older_recent
                        touch_recent_csv(selected_older_recent)
                        state.active_recent_csv_id = selected_older_recent
                        state.active_csv_source = "recent"
                        st.rerun()

        if recent_csvs:
            st.caption(f"Recent files are kept in `{recent_dir()}`.")
            if st.button("Clear recent files", key="clear_recent_csvs"):
                clear_recent_csvs()
                state.active_recent_csv_id = None
                state.active_csv_source = "upload"
                st.rerun()

        if selected_recent_csv_id is None and (
            state.active_csv_source == "recent"
            and state.active_recent_csv_id is not None
        ):
            selected_recent_csv_id = state.active_recent_csv_id
        elif (
            selected_recent_csv_id is None
            and uploaded_file is not None
            and uploaded_signature != state.last_uploaded_csv_signature
        ):
            state.active_csv_source = "upload"
            state.active_recent_csv_id = None
        elif (
            selected_recent_csv_id is None
            and uploaded_file is not None
            and state.active_csv_source == "upload"
        ):
            state.active_recent_csv_id = None

        st.markdown("##### Dashboard")
        dashboards = state.dashboards
        if dashboards:
            name_by_id = {dashboard.id: dashboard.name for dashboard in dashboards}
            ordered = sorted(dashboards, key=lambda dashboard: dashboard.name.lower())

            options = [None] + [dashboard.id for dashboard in ordered]
            selected_index = 0
            if state.active_dashboard_id in options:
                selected_index = options.index(state.active_dashboard_id)
            active_id = st.selectbox(
                "Active dashboard",
                options=options,
                format_func=lambda value: (
                    "(none)" if value is None else name_by_id.get(value, "Unnamed")
                ),
                index=selected_index,
            )
            state.active_dashboard_id = active_id
        else:
            st.info("No dashboards yet. Build one in **Plot Builder** and save it.")
            state.active_dashboard_id = None

        st.caption(
            "Dashboards are saved to `saved_configs.json` (re-rendered on the current CSV)."
        )

    return uploaded_file, selected_recent_csv_id


def render_reading_options() -> ReadOptions:
    """Render the options that control how a CSV file is read."""
    with st.expander("Reading options", expanded=False):
        sep_label = st.selectbox(
            "Separator",
            ["Auto-detect", "Comma (,)", "Semicolon (;)", "Tab (\\t)", "Pipe (|)"],
            index=0,
        )
        sep_map = {
            "Auto-detect": None,
            "Comma (,)": ",",
            "Semicolon (;)": ";",
            "Tab (\\t)": "\t",
            "Pipe (|)": "|",
        }
        sep = sep_map[sep_label]

        decimal_label = st.selectbox("Decimal", ["Dot (.)", "Comma (,)"], index=0)
        decimal = "." if decimal_label == "Dot (.)" else ","

        header_label = st.selectbox(
            "Header",
            [
                "First row",
                "Second row (skip first)",
                "Two rows (multi header)",
                "No header",
            ],
            index=0,
        )
        header: int | tuple[int, ...] | None = 0
        skiprows: tuple[int, ...] | None = None
        if header_label == "Second row (skip first)":
            header, skiprows = 0, (0,)
        elif header_label == "Two rows (multi header)":
            header = (0, 1)
        elif header_label == "No header":
            header = None

        encoding_label = st.selectbox(
            "Encoding",
            list(ENCODING_OPTIONS),
            index=0,
            help="Auto-detect tries UTF-8, then Windows-1252. Change it if accents look wrong.",
        )

    return ReadOptions(
        sep=sep,
        decimal=decimal,
        header=header,
        skiprows=skiprows,
        encoding=ENCODING_OPTIONS[encoding_label],
    )


def upload_signature(uploaded_file) -> str:
    """Identify an uploaded file by name and size (cheap, no content read)."""
    return f"{uploaded_file.name}:{uploaded_file.size}"


def render_date_options(columns: list[str], source_key: str) -> DateSettings:
    """Render the date parsing options for the columns of the loaded file.

    Called after the file is loaded, so the column choices always belong to the
    current file. The detected date column is proposed once per loaded file;
    after that the user's choice, including "(none)", is kept.
    """
    date_guess = guess_date_column(columns)
    options = [None, *columns]

    if state.date_settings_source != source_key or state.read_date_col not in options:
        state.read_date_col = date_guess
        state.date_settings_source = source_key

    if state.read_date_mode not in DATE_PARSE_MODES:
        state.read_date_mode = "Auto-detect"

    with st.sidebar, st.expander("Date parsing", expanded=False):
        st.selectbox(
            "Date/time column (optional)",
            options=options,
            key="read_date_col",
            format_func=lambda value: "(none)" if value is None else str(value),
            help="Used for date parsing, the preview x-axis and date filtering.",
        )
        st.selectbox(
            "Date order",
            options=DATE_PARSE_MODES,
            key="read_date_mode",
            help="Auto-detect infers day/month order from the selected column when possible.",
        )
        st.text_input(
            "Date format override (optional)",
            key="read_date_format",
            help="Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection.",
        )

    return DateSettings(
        column=state.read_date_col,
        mode=state.read_date_mode,
        format=(state.read_date_format or "").strip() or None,
    )
