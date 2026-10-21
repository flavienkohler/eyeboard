"""Compare tab renderer."""

import pandas as pd
import streamlit as st

from plot_studio.config import DATE_PARSE_MODES
from plot_studio.plotting.figures import render_plot_from_spec
from plot_studio.state import remember_recent_config
from plot_studio.services.columns import guess_date_column, resolve_column
from plot_studio.services.csv_reading import read_csv_input
from plot_studio.services.date_parsing import parse_dates_flexible
from plot_studio.services.recent_csvs import (
    format_recent_csv_details,
    get_recent_csv_cache_path,
    list_recent_csvs,
)
from plot_studio.ui.context import MainDatasetContext, ReadingOptions


def render_compare_tab(
    dataset: MainDatasetContext,
    reading_options: ReadingOptions,
) -> None:
    """Render the compare-two-datasets tab."""
    st.markdown("#### Compare (2 CSVs)")
    st.caption("Load two CSVs and compare selected saved plot configs side by side.")

    cmp_left, cmp_right = st.columns(2, vertical_alignment="top")
    recent_csvs = list_recent_csvs(limit=10)
    recent_options = [None] + [entry.get("id") for entry in recent_csvs if entry.get("id")]
    recent_by_id = {
        entry.get("id"): entry for entry in recent_csvs if entry.get("id")
    }
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

    cmp_path_a = (
        str(get_recent_csv_cache_path(cmp_recent_a))
        if cmp_recent_a is not None and cmp_recent_a in recent_by_id
        else ""
    )
    cmp_path_b = (
        str(get_recent_csv_cache_path(cmp_recent_b))
        if cmp_recent_b is not None and cmp_recent_b in recent_by_id
        else ""
    )
    cmp_source_kind_a = "Recent cache" if cmp_path_a else "Upload"
    cmp_source_kind_b = "Recent cache" if cmp_path_b else "Upload"

    cmp_df_a, cmp_label_a, cmp_err_a, _ = read_csv_input(
        None if cmp_path_a else cmp_up_a,
        cmp_path_a,
        decimal=reading_options.decimal,
        sep=reading_options.sep,
        header=reading_options.header,
        skiprows=reading_options.skiprows,
        path_source_kind=cmp_source_kind_a,
    )
    cmp_df_b, cmp_label_b, cmp_err_b, _ = read_csv_input(
        None if cmp_path_b else cmp_up_b,
        cmp_path_b,
        decimal=reading_options.decimal,
        sep=reading_options.sep,
        header=reading_options.header,
        skiprows=reading_options.skiprows,
        path_source_kind=cmp_source_kind_b,
    )

    if cmp_recent_a is not None and cmp_recent_a in recent_by_id:
        cmp_label_a = recent_by_id[cmp_recent_a].get("filename", cmp_label_a)
    if cmp_recent_b is not None and cmp_recent_b in recent_by_id:
        cmp_label_b = recent_by_id[cmp_recent_b].get("filename", cmp_label_b)

    if cmp_err_a:
        st.error(f"Could not read CSV A: {cmp_err_a}")
    if cmp_err_b:
        st.error(f"Could not read CSV B: {cmp_err_b}")

    if cmp_df_a is None or cmp_df_b is None:
        st.info("Provide both Dataset A and Dataset B to compare dashboards.")
        return

    st.caption(
        f"A: `{cmp_label_a or 'CSV A'}` ({len(cmp_df_a):,} rows) | "
        f"B: `{cmp_label_b or 'CSV B'}` ({len(cmp_df_b):,} rows)"
    )

    cmp_configs = st.session_state["saved_configs"]
    if not cmp_configs:
        st.info("No saved plot configs yet. Create one in **Plot Builder** first.")
        return

    cmp_ordered = sorted(cmp_configs, key=lambda cfg: (cfg.get("name") or "").lower())
    cmp_id_to_cfg = {cfg.get("id"): cfg for cfg in cmp_ordered}
    cmp_cfg_options = [cfg.get("id") for cfg in cmp_ordered]

    cmp_active_id = st.session_state.get("active_dashboard_id")
    cmp_default = (
        [cmp_active_id] if cmp_active_id in cmp_cfg_options else cmp_cfg_options[:1]
    )
    cmp_selected_cfg_ids = st.multiselect(
        "Plot configs to compare",
        options=cmp_cfg_options,
        default=cmp_default,
        format_func=lambda value: cmp_id_to_cfg.get(value, {}).get("name", "Unnamed"),
        key="cmp_selected_cfg_ids",
    )

    if cmp_selected_cfg_ids:
        st.session_state["active_dashboard_id"] = cmp_selected_cfg_ids[0]
        remember_recent_config(st.session_state, cmp_selected_cfg_ids[0])

    if not cmp_selected_cfg_ids:
        st.info("Select at least one plot config to compare.")
        return

    compare_state = render_compare_options(dataset, cmp_df_a, cmp_df_b)
    render_compare_results(
        cmp_selected_cfg_ids,
        cmp_id_to_cfg,
        cmp_label_a,
        cmp_label_b,
        compare_state,
    )


def render_compare_options(
    dataset: MainDatasetContext,
    cmp_df_a: pd.DataFrame,
    cmp_df_b: pd.DataFrame,
) -> dict[str, object]:
    """Render compare-specific options and return parsed comparison state."""
    cmp_cols_union = sorted(
        list(set(cmp_df_a.columns).union(set(cmp_df_b.columns))),
        key=lambda col: str(col).lower(),
    )
    cmp_date_guess = st.session_state.get("read_date_col")
    if cmp_date_guess not in cmp_cols_union:
        cmp_date_guess = guess_date_column([str(col) for col in cmp_cols_union])

    with st.expander("Compare options", expanded=False):
        cmp_date_options = [None] + cmp_cols_union
        cmp_date_col = st.selectbox(
            "Shared date/time column (optional)",
            options=cmp_date_options,
            index=(
                cmp_date_options.index(cmp_date_guess)
                if cmp_date_guess in cmp_date_options
                else 0
            ),
            key="cmp_date_col",
        )
        cmp_date_mode_default = st.session_state.get(
            "cmp_date_mode",
            st.session_state.get("read_date_mode", "Auto-detect"),
        )
        if cmp_date_mode_default not in DATE_PARSE_MODES:
            cmp_date_mode_default = "Auto-detect"
        cmp_date_mode = st.selectbox(
            "Date order",
            options=DATE_PARSE_MODES,
            index=DATE_PARSE_MODES.index(cmp_date_mode_default),
            key="cmp_date_mode",
            help="Auto-detect infers day/month order from the selected column when possible.",
        )
        cmp_date_format = st.text_input(
            "Date format override (optional)",
            value=(st.session_state.get("read_date_format", "") or ""),
            key="cmp_date_format",
            help="Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection.",
        ).strip()

    cmp_resolved_date_a = (
        resolve_column(cmp_date_col, list(cmp_df_a.columns)) if cmp_date_col else None
    )
    cmp_resolved_date_b = (
        resolve_column(cmp_date_col, list(cmp_df_b.columns)) if cmp_date_col else None
    )

    cmp_df_a_parsed = parse_dates_flexible(
        cmp_df_a,
        cmp_resolved_date_a,
        date_mode=cmp_date_mode,
        date_format=(cmp_date_format or None),
    )
    cmp_df_b_parsed = parse_dates_flexible(
        cmp_df_b,
        cmp_resolved_date_b,
        date_mode=cmp_date_mode,
        date_format=(cmp_date_format or None),
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
    cmp_selected_cfg_ids: list[str],
    cmp_id_to_cfg: dict[str, dict],
    cmp_label_a: str,
    cmp_label_b: str,
    compare_state: dict[str, object],
) -> None:
    """Render side-by-side comparison charts for the selected configs."""
    for cmp_cfg_id in cmp_selected_cfg_ids:
        cmp_cfg = cmp_id_to_cfg.get(cmp_cfg_id)
        if not cmp_cfg:
            continue

        cmp_plots = cmp_cfg.get("plots") or []
        if not cmp_plots:
            with st.container(border=True):
                st.markdown(f"**{cmp_cfg.get('name', 'Unnamed')}**")
                st.warning("This config contains no plots.")
            continue

        cmp_spec = cmp_plots[0]

        with st.container(border=True):
            st.markdown(f"**{cmp_cfg.get('name', 'Unnamed')}**")
            c_a, c_b = st.columns(2, vertical_alignment="top")

            with c_a:
                st.caption(f"A - {cmp_label_a or 'CSV A'}")
                fig_a, warns_a = render_plot_from_spec(
                    compare_state["cmp_filtered_a"],
                    cmp_spec,
                    compare_state["cmp_avail_a"],
                )
                if warns_a:
                    with st.expander(
                        f"Resolution notes (A) - {cmp_cfg.get('name', 'Unnamed')}",
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
                        key=f"cmp_plot_a_{cmp_cfg_id}",
                    )
                else:
                    st.error("Could not render this config for Dataset A.")

            with c_b:
                st.caption(f"B - {cmp_label_b or 'CSV B'}")
                fig_b, warns_b = render_plot_from_spec(
                    compare_state["cmp_filtered_b"],
                    cmp_spec,
                    compare_state["cmp_avail_b"],
                )
                if warns_b:
                    with st.expander(
                        f"Resolution notes (B) - {cmp_cfg.get('name', 'Unnamed')}",
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
                        key=f"cmp_plot_b_{cmp_cfg_id}",
                    )
                else:
                    st.error("Could not render this config for Dataset B.")
