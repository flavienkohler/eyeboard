"""Sidebar rendering for data selection and reading options."""

import streamlit as st

from eyeboard import __version__
from eyeboard.config import (
    ABOUT_BUTTON_COLOR,
    AUTHOR_GITHUB_URL,
    AUTHOR_LINKEDIN_URL,
    AUTHOR_NAME,
    DATE_PARSE_MODES,
    ENCODING_OPTIONS,
    ISSUES_URL,
    REPO_URL,
)
from eyeboard.i18n import LANGUAGES, t
from eyeboard.models import DateSettings, ReadOptions
from eyeboard.paths import recent_dir
from eyeboard.services.columns import guess_date_column
from eyeboard.services.read_summary import detected_settings
from eyeboard.services.recent_csvs import (
    clear_recent_csvs,
    format_recent_csv_details,
    list_recent_csvs,
    touch_recent_csv,
)
from eyeboard.state import AppState
from eyeboard.ui.context import MainDatasetContext, SidebarSelection
from eyeboard.ui.session import state
from eyeboard.ui.text import escape_markdown

RECENT_BUTTONS = 3


def render_sidebar() -> SidebarSelection:
    """Render the main sidebar and return the current selections."""
    with st.sidebar:
        uploaded_file, recent_csv_id, demo = render_data_section()
        # Filled once the file is loaded, but shown right under the data section.
        status_slot = st.container()
        st.divider()
        read_options = render_reading_options()
        st.selectbox(
            t("Language"),
            list(LANGUAGES),
            format_func=LANGUAGES.__getitem__,
            key="language",
        )
        render_about()

    return SidebarSelection(
        uploaded_file=uploaded_file,
        recent_csv_id=recent_csv_id,
        demo=demo,
        read_options=read_options,
        status_slot=status_slot,
    )


ABOUT_BUTTON_STYLE = f"""
<style>
section[data-testid="stSidebar"] [data-testid="stPopoverButton"] {{
    background-color: {ABOUT_BUTTON_COLOR};
    border-color: {ABOUT_BUTTON_COLOR};
    color: #0f2a1d;
    font-weight: 600;
}}
section[data-testid="stSidebar"] [data-testid="stPopoverButton"]:hover {{
    background-color: #5cc78a;
    border-color: #5cc78a;
    color: #0f2a1d;
}}
</style>
"""


def render_about() -> None:
    """A small box with the version, the author's links and where to send feedback."""
    st.html(ABOUT_BUTTON_STYLE)
    with st.popover(t("About")):
        st.markdown(f"**EyeBoard** {__version__}")
        st.caption(t("Made by {author}", author=AUTHOR_NAME))
        links = [f"[GitHub]({AUTHOR_GITHUB_URL})"]
        if AUTHOR_LINKEDIN_URL:
            links.append(f"[LinkedIn]({AUTHOR_LINKEDIN_URL})")
        st.markdown("  ·  ".join(links))
        st.markdown(
            t("Ideas, bugs, questions: [open an issue]({url}).", url=ISSUES_URL)
        )
        st.caption(
            t(
                "Free for noncommercial use ([license]({url})).",
                url=f"{REPO_URL}/blob/main/LICENSE",
            )
        )


def choose_active_source(state: AppState, uploaded_signature: str | None) -> str | None:
    """Decide which file is active and return the recent file to open, if any.

    A file uploaded just now wins over the recent file that was open. Without a
    new upload, the recent file stays active until another source is chosen.
    The upload signature is recorded once the file is loaded, so a rerun with
    the same upload does not override a recent file picked afterwards.
    """
    is_new_upload = (
        uploaded_signature is not None
        and uploaded_signature != state.last_uploaded_csv_signature
    )
    if is_new_upload:
        state.active_csv_source = "upload"
        state.active_recent_csv_id = None
        return None
    if state.active_csv_source == "recent" and state.active_recent_csv_id is not None:
        return state.active_recent_csv_id
    if uploaded_signature is not None:
        state.active_recent_csv_id = None
    return None


def open_recent_csv(entry_id: str) -> None:
    """Make a recent file the active one and rerun the page."""
    touch_recent_csv(entry_id)
    state.active_recent_csv_id = entry_id
    state.active_csv_source = "recent"
    st.rerun()


def render_data_section():
    """Render the file upload and the list of recent files."""
    with st.expander(t("Data"), expanded=True):
        uploaded_file = st.file_uploader(
            t("Upload CSV"),
            type=["csv"],
            help=t("Upload a CSV file from your computer."),
            key="data_upload",
        )
        if st.button(t("Try the demo data"), key="try_demo", width="stretch"):
            state.active_csv_source = "demo"
            state.active_recent_csv_id = None
            st.rerun()
        recent_csvs = list_recent_csvs()
        if recent_csvs:
            render_recent_files(recent_csvs)

    signature = upload_signature(uploaded_file) if uploaded_file is not None else None
    recent_id = choose_active_source(state, signature)
    return uploaded_file, recent_id, state.active_csv_source == "demo"


def render_recent_files(recent_csvs: list[dict]) -> None:
    """Render the recent files: the latest as buttons, the others in a list."""
    st.caption(t("Recent CSVs"))
    for entry in recent_csvs[:RECENT_BUTTONS]:
        entry_id = entry.get("id")
        is_active = (
            state.active_csv_source == "recent"
            and state.active_recent_csv_id == entry_id
        )
        if st.button(
            entry.get("filename", t("Unnamed CSV")),
            key=f"recent_csv_{entry_id}",
            width="stretch",
            type="primary" if is_active else "secondary",
        ):
            open_recent_csv(entry_id)
        st.caption(format_recent_csv_details(entry))

    older = {
        entry["id"]: entry for entry in recent_csvs[RECENT_BUTTONS:] if entry.get("id")
    }
    if older:
        chosen = st.selectbox(
            t("Older recent CSVs"),
            options=[None, *older],
            format_func=lambda value: (
                t("Choose an older recent CSV")
                if value is None
                else older[value].get("filename", t("Unnamed CSV"))
            ),
            help=t("Scroll through older recently opened CSVs."),
        )
        if chosen is not None:
            st.caption(format_recent_csv_details(older[chosen]))
            if st.button(
                t("Open selected recent CSV"),
                key="open_older_recent_csv",
                width="stretch",
            ):
                open_recent_csv(chosen)

    st.caption(t("Recent files are kept in `{folder}`.", folder=recent_dir()))
    if st.button(t("Clear recent files"), key="clear_recent_csvs"):
        clear_recent_csvs()
        state.active_recent_csv_id = None
        if state.active_csv_source == "recent":
            state.active_csv_source = "upload"
        st.rerun()


def render_status_card(dataset: MainDatasetContext) -> None:
    """Summarise the loaded file: its size, how it was read and any warnings."""
    with st.container(border=True):
        st.markdown(f"**{escape_markdown(dataset.label or 'CSV')}**")
        st.caption(
            t(
                "{rows:,} rows x {columns:,} columns",
                rows=len(dataset.df),
                columns=len(dataset.cols),
            )
        )
        if dataset.read_report is not None:
            settings = detected_settings(
                dataset.read_report,
                dataset.read_options,
                dataset.date_settings,
                dataset.date_order,
            )
            st.caption("  \n".join(f"{t(s.name)}: {s.text()}" for s in settings))
        if dataset.date_col and dataset.date_parse_candidate_count > 0:
            rate = dataset.date_parse_success_count / dataset.date_parse_candidate_count
            st.caption(t("Dates parsed: {rate:.0%}", rate=rate))
        problems = len(dataset.read_report.warnings) if dataset.read_report else 0
        problems += bool(dataset.date_parse_warning)
        problems += sum(1 for p in dataset.profiles if p.decimal_comma)
        if problems:
            st.caption(
                t(":orange[{problems} warning(s), see Explore]", problems=problems)
            )


def render_reading_options() -> ReadOptions:
    """Render the options that control how a CSV file is read."""
    with st.expander(t("Reading options"), expanded=False):
        sep_label = st.selectbox(
            t("Separator"),
            ["Auto-detect", "Comma (,)", "Semicolon (;)", "Tab (\\t)", "Pipe (|)"],
            index=0,
            format_func=t,
            key="read_sep",
        )
        sep_map = {
            "Auto-detect": None,
            "Comma (,)": ",",
            "Semicolon (;)": ";",
            "Tab (\\t)": "\t",
            "Pipe (|)": "|",
        }
        sep = sep_map[sep_label]

        decimal_label = st.selectbox(
            t("Decimal"),
            ["Dot (.)", "Comma (,)"],
            index=0,
            format_func=t,
            key="read_decimal",
        )
        decimal = "." if decimal_label == "Dot (.)" else ","

        header_label = st.selectbox(
            t("Header"),
            [
                "First row",
                "Second row (skip first)",
                "Two rows (multi header)",
                "No header",
            ],
            index=0,
            format_func=t,
            key="read_header",
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
            t("Encoding"),
            list(ENCODING_OPTIONS),
            index=0,
            format_func=t,
            key="read_encoding",
            help=t(
                "Auto-detect tries UTF-8, then Windows-1252. Change it if accents look wrong."
            ),
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

    with st.sidebar, st.expander(t("Date parsing"), expanded=False):
        st.selectbox(
            t("Date/time column (optional)"),
            options=options,
            key="read_date_col",
            format_func=lambda value: t("(none)") if value is None else str(value),
            help=t("Used for date parsing, the preview x-axis and date filtering."),
        )
        st.selectbox(
            t("Date order"),
            options=DATE_PARSE_MODES,
            key="read_date_mode",
            format_func=t,
            help=t(
                "Auto-detect infers day/month order from the selected column when possible."
            ),
        )
        st.text_input(
            t("Date format override (optional)"),
            key="read_date_format",
            help=t(
                "Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection."
            ),
        )

    return DateSettings(
        column=state.read_date_col,
        mode=state.read_date_mode,
        format=(state.read_date_format or "").strip() or None,
    )
