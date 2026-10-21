"""Header and summary UI components."""

import streamlit as st

from plot_studio.config import APP_HEADER_SUBTITLE, APP_HEADER_TITLE
from plot_studio.ui.context import MainDatasetContext


def render_header() -> None:
    """Render the app header."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom: 6px;">
          <div>
            <div style="font-size: 28px; font-weight: 800; line-height: 1.0;">{APP_HEADER_TITLE}</div>
            <div style="font-size: 14px; opacity: 0.85; margin-top: 6px;">
              {APP_HEADER_SUBTITLE}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dataset_summary(dataset: MainDatasetContext) -> None:
    """Render top-of-page dataset summary metrics."""
    left, right = st.columns([2, 1], vertical_alignment="top")
    with left:
        st.markdown(f"#### Data: `{dataset.label or 'CSV'}`")
    with right:
        st.markdown("")
        action_col, tip_col = st.columns([0.7, 1.3], vertical_alignment="center")
        with action_col:
            if st.button("Reload CSV", key="reload_current_csv", width="stretch"):
                st.rerun()
        with tip_col:
            st.caption(
                "Tip: Use **Dashboard** for consistent plots across different CSVs."
            )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows", f"{len(dataset.df):,}")
    m2.metric("Columns", f"{len(dataset.cols):,}")
    m3.metric("Missing cells", f"{int(dataset.df.isna().sum().sum()):,}")
    m4.metric(
        "Memory (approx.)",
        f"{dataset.df.memory_usage(deep=True).sum() / (1024**2):.1f} MB",
    )

    st.divider()


def render_read_report(dataset: MainDatasetContext) -> None:
    """Render a compact report describing how the current CSV was interpreted."""
    read_report = dataset.read_report
    if read_report is None:
        return

    parse_summary = "Not used"
    if dataset.date_col:
        if dataset.date_parse_candidate_count > 0:
            success_rate = (
                dataset.date_parse_success_count / dataset.date_parse_candidate_count
            )
            parse_summary = (
                f"{dataset.date_parse_success_count:,}/{dataset.date_parse_candidate_count:,} "
                f"({success_rate:.0%})"
            )
        else:
            parse_summary = "No non-empty values"

    with st.container(border=True):
        title_col, source_col = st.columns([1.4, 1], vertical_alignment="center")
        with title_col:
            st.caption("Read report")
        with source_col:
            st.caption(
                f"{read_report.source_kind}: `{read_report.source_label or dataset.label}`"
            )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Separator", read_report.separator_label)
        c2.metric("Decimal", read_report.decimal_label)
        c3.metric("Header", read_report.header_label)
        c4.metric("Date Parse", parse_summary)

        date_details = (
            f"Date column: `{dataset.date_col}` | Mode: `{dataset.date_parse_mode}`"
            if dataset.date_col
            else "Date column: `(none selected)`"
        )
        if dataset.date_format:
            date_details += f" | Format override: `{dataset.date_format}`"
        st.caption(date_details)

        for warning in read_report.warnings:
            st.warning(warning)
        if dataset.date_parse_warning:
            st.warning(dataset.date_parse_warning)
