"""Sidebar rendering for data selection and reading options."""

import pandas as pd
import streamlit as st

from plot_studio.config import DATE_PARSE_MODES
from plot_studio.services.recent_csvs import (
    format_recent_csv_details,
    list_recent_csvs,
    touch_recent_csv,
)
from plot_studio.services.columns import guess_date_column
from plot_studio.ui.context import ReadingOptions, SidebarSelection


def render_sidebar() -> SidebarSelection:
    """Render the main sidebar and return the current selections."""
    with st.sidebar:
        uploaded_file, recent_csv_id = render_data_section()
        st.divider()
        reading_options = render_reading_options()

    return SidebarSelection(
        uploaded_file=uploaded_file,
        recent_csv_id=recent_csv_id,
        reading_options=reading_options,
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
            uploaded_signature = f"{uploaded_file.name}:{len(uploaded_file.getvalue())}"

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
                        if st.session_state.get("active_recent_csv_id") == entry_id
                        and st.session_state.get("active_csv_source") == "recent"
                        else "secondary"
                    ),
                ):
                    selected_recent_csv_id = entry_id
                    touch_recent_csv(entry_id)
                    st.session_state["active_recent_csv_id"] = entry_id
                    st.session_state["active_csv_source"] = "recent"
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
                        st.session_state["active_recent_csv_id"] = (
                            selected_older_recent
                        )
                        st.session_state["active_csv_source"] = "recent"
                        st.rerun()

        if selected_recent_csv_id is None and (
            st.session_state.get("active_csv_source") == "recent"
            and st.session_state.get("active_recent_csv_id") is not None
        ):
            selected_recent_csv_id = st.session_state["active_recent_csv_id"]
        elif (
            selected_recent_csv_id is None
            and uploaded_file is not None
            and uploaded_signature
            != st.session_state.get("last_uploaded_csv_signature")
        ):
            st.session_state["active_csv_source"] = "upload"
            st.session_state["active_recent_csv_id"] = None
        elif (
            selected_recent_csv_id is None
            and uploaded_file is not None
            and st.session_state.get("active_csv_source") == "upload"
        ):
            st.session_state["active_recent_csv_id"] = None

        st.markdown("##### Dashboard")
        configs = st.session_state["saved_configs"]
        if configs:
            name_by_id = {cfg.get("id"): cfg.get("name", "Unnamed") for cfg in configs}
            ordered = sorted(configs, key=lambda cfg: (cfg.get("name") or "").lower())

            options = [None] + [cfg.get("id") for cfg in ordered]
            selected_index = 0
            if st.session_state["active_dashboard_id"] in options:
                selected_index = options.index(st.session_state["active_dashboard_id"])
            active_id = st.selectbox(
                "Active dashboard",
                options=options,
                format_func=lambda value: (
                    "(none)" if value is None else name_by_id.get(value, "Unnamed")
                ),
                index=selected_index,
            )
            st.session_state["active_dashboard_id"] = active_id
        else:
            st.info("No dashboards yet. Build one in **Plot Builder** and save it.")
            st.session_state["active_dashboard_id"] = None

        st.caption(
            "Dashboards are saved to `saved_configs.json` (re-rendered on the current CSV)."
        )

    return uploaded_file, selected_recent_csv_id


def render_reading_options() -> ReadingOptions:
    """Render the shared CSV and date parsing options."""
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
        header: int | list[int] | None = 0
        skiprows: list[int] | None = None
        if header_label == "Second row (skip first)":
            header, skiprows = 0, [0]
        elif header_label == "Two rows (multi header)":
            header = [0, 1]
        elif header_label == "No header":
            header = None

        st.markdown("##### Date parsing")
        sidebar_df = st.session_state.get("df")
        sidebar_cols = (
            list(sidebar_df.columns) if isinstance(sidebar_df, pd.DataFrame) else []
        )
        sidebar_date_guess = guess_date_column(sidebar_cols) if sidebar_cols else None
        date_options = [None] + sidebar_cols if sidebar_cols else [None]

        current_sidebar_date_col = st.session_state.get("read_date_col")
        if current_sidebar_date_col not in date_options:
            current_sidebar_date_col = (
                sidebar_date_guess if sidebar_date_guess in date_options else None
            )
            st.session_state["read_date_col"] = current_sidebar_date_col

        st.selectbox(
            "Date/time column (optional)",
            options=date_options,
            index=(
                date_options.index(current_sidebar_date_col)
                if current_sidebar_date_col in date_options
                else 0
            ),
            key="read_date_col",
            format_func=lambda value: "(none)" if value is None else str(value),
            disabled=(len(sidebar_cols) == 0),
            help="Used for date parsing, mini-plots x-axis, and Plot Builder date filtering.",
        )

        current_date_mode = st.session_state.get("read_date_mode", "Auto-detect")
        if current_date_mode not in DATE_PARSE_MODES:
            current_date_mode = "Auto-detect"
            st.session_state["read_date_mode"] = current_date_mode
        st.selectbox(
            "Date order",
            options=DATE_PARSE_MODES,
            index=DATE_PARSE_MODES.index(current_date_mode),
            key="read_date_mode",
            help="Auto-detect infers day/month order from the selected column when possible.",
        )
        st.text_input(
            "Date format override (optional)",
            key="read_date_format",
            help="Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection.",
        )

    date_format_input = (st.session_state.get("read_date_format", "") or "").strip()
    return ReadingOptions(
        sep=sep,
        decimal=decimal,
        header=header,
        skiprows=skiprows,
        date_mode=st.session_state.get("read_date_mode", "Auto-detect"),
        date_format=date_format_input or None,
    )
