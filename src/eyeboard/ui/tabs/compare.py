"""Compare tab renderer."""

from dataclasses import replace

import pandas as pd
import streamlit as st

from eyeboard.dashboards.model import Dashboard
from eyeboard.models import ReadOptions
from eyeboard.plotting.figures import render_plot_from_spec
from eyeboard.services.columns import resolve_column
from eyeboard.services.dataset import DataSource, source_from_path, source_from_upload
from eyeboard.services.recent_csvs import (
    format_recent_csv_details,
    get_recent_csv_cache_path,
    list_recent_csvs,
)
from eyeboard.state import remember_recent_dashboard
from eyeboard.ui.cache import load_table_cached, parse_table_cached
from eyeboard.ui.context import MainDatasetContext
from eyeboard.ui.text import escape_markdown


def _compare_source(
    uploaded_file: object,
    recent_id: str | None,
    recent_by_id: dict[str, dict],
) -> DataSource | None:
    """Pick the data source of one compared dataset (a recent file wins)."""
    if recent_id is not None and recent_id in recent_by_id:
        path = get_recent_csv_cache_path(recent_id)
        if path.exists():
            return source_from_path(
                path,
                kind="Recent cache",
                label=recent_by_id[recent_id].get("filename") or path.name,
            )
    if uploaded_file is not None:
        return source_from_upload(uploaded_file)
    return None


def _load_compare_dataset(
    name: str,
    source: DataSource | None,
    options: ReadOptions,
) -> tuple[pd.DataFrame | None, str]:
    """Load one compared dataset through the cache, reporting read errors."""
    if source is None:
        return None, ""
    df, _, error = load_table_cached(source, options)
    if error:
        st.error(f"Could not read CSV {name}: {error}")
    return df, source.label


def _parse_compare_dataset(
    dataset: MainDatasetContext,
    source: DataSource,
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    """Parse the date column of a compared dataset with the shared date settings.

    The date column chosen for the main dataset is matched by name in the compared
    file; returns the parsed table and the matched column (or ``None``).
    """
    settings = dataset.date_settings
    column = (
        resolve_column(settings.column, list(df.columns)) if settings.column else None
    )
    parsed = parse_table_cached(
        source, dataset.read_options, replace(settings, column=column), df
    )
    return parsed.df, column


def render_compare_tab(dataset: MainDatasetContext) -> None:
    """Render the compare-two-datasets tab."""
    st.markdown("#### Compare (2 CSVs)")
    st.caption("Load two CSVs and compare selected saved plot dashboards side by side.")

    cmp_left, cmp_right = st.columns(2, vertical_alignment="top")
    recent_csvs = list_recent_csvs(limit=10)
    recent_options = [None] + [
        entry.get("id") for entry in recent_csvs if entry.get("id")
    ]
    recent_by_id = {entry.get("id"): entry for entry in recent_csvs if entry.get("id")}
    with cmp_left:
        st.markdown("##### Dataset A")
        cmp_up_a = st.file_uploader("Upload CSV A", type=["csv"], key="cmp_up_a")
        cmp_recent_a = st.selectbox(
            "Recent CSV for A",
            options=recent_options,
            index=0,
            format_func=lambda value: (
                "Choose a recent CSV"
                if value is None
                else recent_by_id.get(value, {}).get("filename", "Unnamed CSV")
            ),
            key="cmp_recent_csv_a",
            help="Optional. If selected, this cached recent CSV is used for Dataset A.",
        )
        if cmp_recent_a is not None and cmp_recent_a in recent_by_id:
            st.caption(format_recent_csv_details(recent_by_id[cmp_recent_a]))
    with cmp_right:
        st.markdown("##### Dataset B")
        cmp_up_b = st.file_uploader("Upload CSV B", type=["csv"], key="cmp_up_b")
        cmp_recent_b = st.selectbox(
            "Recent CSV for B",
            options=recent_options,
            index=0,
            format_func=lambda value: (
                "Choose a recent CSV"
                if value is None
                else recent_by_id.get(value, {}).get("filename", "Unnamed CSV")
            ),
            key="cmp_recent_csv_b",
            help="Optional. If selected, this cached recent CSV is used for Dataset B.",
        )
        if cmp_recent_b is not None and cmp_recent_b in recent_by_id:
            st.caption(format_recent_csv_details(recent_by_id[cmp_recent_b]))

    cmp_source_a = _compare_source(cmp_up_a, cmp_recent_a, recent_by_id)
    cmp_source_b = _compare_source(cmp_up_b, cmp_recent_b, recent_by_id)
    cmp_df_a, cmp_label_a = _load_compare_dataset(
        "A", cmp_source_a, dataset.read_options
    )
    cmp_df_b, cmp_label_b = _load_compare_dataset(
        "B", cmp_source_b, dataset.read_options
    )

    if cmp_df_a is None or cmp_df_b is None:
        st.info("Provide both Dataset A and Dataset B to compare dashboards.")
        return

    st.caption(
        f"A: `{cmp_label_a or 'CSV A'}` ({len(cmp_df_a):,} rows) | "
        f"B: `{cmp_label_b or 'CSV B'}` ({len(cmp_df_b):,} rows)"
    )

    cmp_dashboards = st.session_state["dashboards"]
    if not cmp_dashboards:
        st.info("No saved plot dashboards yet. Create one in **Plot Builder** first.")
        return

    cmp_ordered = sorted(cmp_dashboards, key=lambda dashboard: dashboard.name.lower())
    cmp_dashboards_by_id = {dashboard.id: dashboard for dashboard in cmp_ordered}
    cmp_dashboard_options = [dashboard.id for dashboard in cmp_ordered]

    cmp_active_id = st.session_state.get("active_dashboard_id")
    cmp_default = (
        [cmp_active_id]
        if cmp_active_id in cmp_dashboard_options
        else cmp_dashboard_options[:1]
    )
    cmp_selected_dashboard_ids = st.multiselect(
        "Dashboards to compare",
        options=cmp_dashboard_options,
        default=cmp_default,
        format_func=lambda value: cmp_dashboards_by_id[value].name,
        key="cmp_selected_dashboard_ids",
    )

    if cmp_selected_dashboard_ids:
        st.session_state["active_dashboard_id"] = cmp_selected_dashboard_ids[0]
        remember_recent_dashboard(st.session_state, cmp_selected_dashboard_ids[0])

    if not cmp_selected_dashboard_ids:
        st.info("Select at least one dashboard to compare.")
        return

    compare_state = render_compare_options(
        dataset, cmp_source_a, cmp_df_a, cmp_source_b, cmp_df_b
    )
    render_compare_results(
        cmp_selected_dashboard_ids,
        cmp_dashboards_by_id,
        cmp_label_a,
        cmp_label_b,
        compare_state,
    )


def render_compare_options(
    dataset: MainDatasetContext,
    cmp_source_a: DataSource,
    cmp_df_a: pd.DataFrame,
    cmp_source_b: DataSource,
    cmp_df_b: pd.DataFrame,
) -> dict[str, object]:
    """Parse both datasets with the shared date settings and apply the shared range."""
    cmp_df_a_parsed, cmp_resolved_date_a = _parse_compare_dataset(
        dataset, cmp_source_a, cmp_df_a
    )
    cmp_df_b_parsed, cmp_resolved_date_b = _parse_compare_dataset(
        dataset, cmp_source_b, cmp_df_b
    )

    cmp_filtered_a = cmp_df_a_parsed
    cmp_filtered_b = cmp_df_b_parsed

    if (
        cmp_resolved_date_a
        and cmp_resolved_date_b
        and cmp_resolved_date_a in cmp_df_a_parsed.columns
        and cmp_resolved_date_b in cmp_df_b_parsed.columns
    ):
        dt_a = cmp_df_a_parsed[cmp_resolved_date_a]
        dt_b = cmp_df_b_parsed[cmp_resolved_date_b]
        if pd.api.types.is_datetime64_any_dtype(
            dt_a
        ) and pd.api.types.is_datetime64_any_dtype(dt_b):
            valid_a = dt_a.dropna()
            valid_b = dt_b.dropna()
            if not valid_a.empty and not valid_b.empty:
                overlap_min = max(valid_a.min(), valid_b.min())
                overlap_max = min(valid_a.max(), valid_b.max())
                if overlap_min <= overlap_max:
                    with st.expander("Shared date range filter", expanded=False):
                        cmp_range = st.slider(
                            "Filter shared date range",
                            min_value=overlap_min.to_pydatetime(),
                            max_value=overlap_max.to_pydatetime(),
                            value=(
                                overlap_min.to_pydatetime(),
                                overlap_max.to_pydatetime(),
                            ),
                            key="cmp_dateslider",
                        )
                    cmp_filtered_a = cmp_df_a_parsed[
                        (cmp_df_a_parsed[cmp_resolved_date_a] >= cmp_range[0])
                        & (cmp_df_a_parsed[cmp_resolved_date_a] <= cmp_range[1])
                    ]
                    cmp_filtered_b = cmp_df_b_parsed[
                        (cmp_df_b_parsed[cmp_resolved_date_b] >= cmp_range[0])
                        & (cmp_df_b_parsed[cmp_resolved_date_b] <= cmp_range[1])
                    ]
                    if cmp_filtered_a.empty or cmp_filtered_b.empty:
                        st.warning(
                            "The shared date range leaves at least one comparison dataset empty."
                        )

    return {
        "cmp_filtered_a": cmp_filtered_a,
        "cmp_filtered_b": cmp_filtered_b,
        "cmp_avail_a": list(cmp_filtered_a.columns),
        "cmp_avail_b": list(cmp_filtered_b.columns),
    }


def render_compare_results(
    cmp_selected_dashboard_ids: list[str],
    cmp_dashboards_by_id: dict[str, Dashboard],
    cmp_label_a: str,
    cmp_label_b: str,
    compare_state: dict[str, object],
) -> None:
    """Render side-by-side comparison charts for the selected dashboards."""
    for cmp_dashboard_id in cmp_selected_dashboard_ids:
        cmp_dashboard = cmp_dashboards_by_id.get(cmp_dashboard_id)
        if not cmp_dashboard:
            continue

        cmp_plots = cmp_dashboard.plots
        if not cmp_plots:
            with st.container(border=True):
                st.markdown(f"**{escape_markdown(cmp_dashboard.name)}**")
                st.warning("This dashboard contains no plots.")
            continue

        cmp_spec = cmp_plots[0]

        with st.container(border=True):
            st.markdown(f"**{escape_markdown(cmp_dashboard.name)}**")
            c_a, c_b = st.columns(2, vertical_alignment="top")

            with c_a:
                st.caption(f"A - {escape_markdown(cmp_label_a or 'CSV A')}")
                fig_a, warns_a = render_plot_from_spec(
                    compare_state["cmp_filtered_a"],
                    cmp_spec,
                    compare_state["cmp_avail_a"],
                )
                if warns_a:
                    with st.expander(
                        f"Resolution notes (A) - {cmp_dashboard.name}",
                        expanded=False,
                    ):
                        for warning in warns_a:
                            if warning.startswith("Matched "):
                                st.info(warning)
                            else:
                                st.warning(warning)
                if fig_a is not None:
                    st.plotly_chart(
                        fig_a,
                        width="stretch",
                        key=f"cmp_plot_a_{cmp_dashboard_id}",
                    )
                else:
                    st.error("Could not render this dashboard for Dataset A.")

            with c_b:
                st.caption(f"B - {escape_markdown(cmp_label_b or 'CSV B')}")
                fig_b, warns_b = render_plot_from_spec(
                    compare_state["cmp_filtered_b"],
                    cmp_spec,
                    compare_state["cmp_avail_b"],
                )
                if warns_b:
                    with st.expander(
                        f"Resolution notes (B) - {cmp_dashboard.name}",
                        expanded=False,
                    ):
                        for warning in warns_b:
                            if warning.startswith("Matched "):
                                st.info(warning)
                            else:
                                st.warning(warning)
                if fig_b is not None:
                    st.plotly_chart(
                        fig_b,
                        width="stretch",
                        key=f"cmp_plot_b_{cmp_dashboard_id}",
                    )
                else:
                    st.error("Could not render this dashboard for Dataset B.")
