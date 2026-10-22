"""Header and summary UI components."""

import streamlit as st

from eyeboard.config import APP_HEADER_SUBTITLE, APP_HEADER_TITLE
from eyeboard.i18n import t
from eyeboard.services.read_summary import detected_settings
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.text import escape_markdown


def render_header() -> None:
    """Render the app header."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom: 6px;">
          <div>
            <div style="font-size: 28px; font-weight: 800; line-height: 1.0;">{APP_HEADER_TITLE}</div>
            <div style="font-size: 14px; opacity: 0.85; margin-top: 6px;">
              {t(APP_HEADER_SUBTITLE)}
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
        st.markdown(
            t("#### Data: {name}", name=escape_markdown(dataset.label or "CSV"))
        )
    with right:
        st.markdown("")
        action_col, tip_col = st.columns([0.7, 1.3], vertical_alignment="center")
        with action_col:
            if st.button(t("Reload CSV"), key="reload_current_csv", width="stretch"):
                st.rerun()
        with tip_col:
            st.caption(
                t("Tip: Use **Dashboards** for consistent plots across different CSVs.")
            )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("Rows"), f"{len(dataset.df):,}")
    m2.metric(t("Columns"), f"{len(dataset.cols):,}")
    m3.metric(t("Missing cells"), f"{int(dataset.df.isna().sum().sum()):,}")
    m4.metric(
        t("Memory (approx.)"),
        f"{dataset.df.memory_usage(deep=True).sum() / (1024**2):.1f} MB",
    )

    st.divider()


def render_read_report(dataset: MainDatasetContext) -> None:
    """Render a compact report describing how the current CSV was interpreted."""
    read_report = dataset.read_report
    if read_report is None:
        return

    parse_summary = t("Not used")
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
            parse_summary = t("No non-empty values")

    with st.container(border=True):
        title_col, source_col = st.columns([1.4, 1], vertical_alignment="center")
        with title_col:
            st.caption(t("Read report"))
        with source_col:
            st.caption(
                f"{t(read_report.source_kind)}: `{read_report.source_label or dataset.label}`"
            )

        by_name = {
            setting.name: setting.text()
            for setting in detected_settings(
                read_report,
                dataset.read_options,
                dataset.date_settings,
                dataset.date_order,
            )
        }
        facts = [
            (t("Separator"), by_name["Separator"]),
            (t("Decimal"), by_name["Decimal"]),
            (t("Encoding"), by_name["Encoding"]),
            (t("Header"), by_name["Header"]),
            (t("Date order"), by_name.get("Date order", t("n/a"))),
            (t("Date parse"), parse_summary),
        ]
        # Plain text, not st.metric: metrics cut long values ("Semicolon (;) (auto)").
        for column, (label, value) in zip(st.columns(len(facts)), facts, strict=True):
            column.caption(label)
            column.markdown(f"**{value}**")

        date_details = (
            t(
                "Date column: `{column}` | Mode: `{mode}`",
                column=dataset.date_col,
                mode=t(dataset.date_parse_mode),
            )
            if dataset.date_col
            else t("Date column: `(none selected)`")
        )
        if dataset.date_format:
            date_details += t(
                " | Format override: `{format}`", format=dataset.date_format
            )
        st.caption(date_details + t(". (auto) means EyeBoard found it, not you."))

        for warning in read_report.warnings:
            st.warning(warning)
        if dataset.date_parse_warning:
            st.warning(dataset.date_parse_warning)
