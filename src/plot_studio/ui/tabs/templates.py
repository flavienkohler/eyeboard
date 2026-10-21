"""Dashboards manager tab renderer."""

import datetime
import json
import uuid

import streamlit as st

from plot_studio.config import PLOT_TYPES, TEMPLATES
from plot_studio.plotting.figures import render_plot_from_spec
from plot_studio.plotting.specs import build_plot_spec_from_builder
from plot_studio.state import prune_recent_config_ids
from plot_studio.services.columns import normalize_colname
from plot_studio.services.templates import remove_dashboard_plot
from plot_studio.services.templates import persist_saved_configs_to_disk
from plot_studio.services.templates import update_dashboard_plot
from plot_studio.services.templates import validate_saved_config
from plot_studio.ui.context import MainDatasetContext


def _persist_configs_with_feedback(
    new_configs: list[dict],
    *,
    success_message: str,
) -> bool:
    """Persist dashboards and show success/error feedback."""
    save_error = persist_saved_configs_to_disk(new_configs)
    if save_error:
        st.error(save_error)
        return False

    st.session_state["saved_configs"] = new_configs
    st.session_state["saved_configs_load_error"] = None
    prune_recent_config_ids(st.session_state)
    st.success(success_message)
    return True


def render_templates_tab(dataset: MainDatasetContext) -> None:
    """Render dashboard management UI."""
    st.markdown("#### Dashboards Manager")
    st.caption(
        "Manage dashboards, edit or remove individual plots, export/import, and edit JSON."
    )

    configs = st.session_state["saved_configs"]
    if not configs:
        st.info("No dashboards saved yet.")
        return

    ordered = sorted(configs, key=lambda cfg: (cfg.get("name") or "").lower())
    id_to_cfg = {cfg.get("id"): cfg for cfg in ordered}
    sel_id = st.selectbox(
        "Select dashboard",
        options=[cfg.get("id") for cfg in ordered],
        format_func=lambda value: id_to_cfg[value].get("name", "Unnamed"),
    )
    sel = id_to_cfg.get(sel_id)
    selected_config_errors = validate_saved_config(sel)
    if selected_config_errors:
        st.error("This dashboard could not be read correctly.")
        for error in selected_config_errors:
            st.warning(error)

    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="top")
    with c1:
        new_name = st.text_input("Rename", value=sel.get("name", ""))
        if st.button("Apply rename", width="stretch"):
            renamed_config = dict(sel)
            renamed_config["name"] = new_name.strip() or sel.get("name", "")
            new_configs = [
                renamed_config if cfg.get("id") == sel_id else cfg for cfg in configs
            ]
            _persist_configs_with_feedback(new_configs, success_message="Renamed.")
    with c2:
        st.download_button(
            "Export selected (JSON)",
            data=json.dumps(sel, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=(
                f"{normalize_colname(sel.get('name', 'dashboard')).replace(' ', '_') or 'dashboard'}.json"
            ),
            mime="application/json",
            width="stretch",
        )
    with c3:
        if st.button("Delete selected", type="secondary", width="stretch"):
            new_configs = [cfg for cfg in configs if cfg.get("id") != sel_id]
            if _persist_configs_with_feedback(new_configs, success_message="Deleted."):
                if st.session_state.get("active_dashboard_id") == sel_id:
                    st.session_state["active_dashboard_id"] = None
                st.rerun()

    st.divider()
    render_dashboard_plot_editor(sel, configs, dataset)

    st.divider()

    with st.expander("Edit dashboard JSON (advanced)", expanded=False):
        edited = st.text_area(
            "Dashboard JSON",
            value=json.dumps(sel, ensure_ascii=False, indent=2),
            height=380,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Validate JSON", width="stretch"):
                try:
                    json.loads(edited)
                    st.success("Valid JSON.")
                except Exception as exc:
                    st.error(f"Invalid JSON: {exc}")
        with col_b:
            if st.button("Save JSON to dashboard", width="stretch"):
                try:
                    new_obj = json.loads(edited)
                    if not isinstance(new_obj, dict):
                        st.error("Dashboard JSON must be an object.")
                    else:
                        new_obj.setdefault("id", sel_id)
                        validation_errors = validate_saved_config(new_obj)
                        if validation_errors:
                            st.error("Dashboard JSON is structurally invalid.")
                            for error in validation_errors:
                                st.warning(error)
                            return
                        new_configs = []
                        for cfg in configs:
                            if cfg.get("id") == sel_id:
                                new_configs.append(new_obj)
                            else:
                                new_configs.append(cfg)
                        if _persist_configs_with_feedback(
                            new_configs,
                            success_message="Dashboard updated.",
                        ):
                            st.rerun()
                except Exception as exc:
                    st.error(f"Could not save: {exc}")

    st.divider()
    st.markdown("##### Import dashboard JSON")
    upl = st.file_uploader(
        "Import a dashboard (.json)", type=["json"], key="import_json"
    )
    if upl is not None:
        upload_signature = f"{upl.name}:{len(upl.getvalue())}"
        if upload_signature != st.session_state.get("last_imported_json_signature"):
            try:
                imported = json.loads(upl.getvalue().decode("utf-8"))
                if not isinstance(imported, dict):
                    st.error("Imported file must be a JSON object.")
                else:
                    imported.setdefault("id", str(uuid.uuid4()))
                    imported.setdefault(
                        "created_at",
                        datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    imported.setdefault("plots", [])
                    validation_errors = validate_saved_config(imported)
                    if validation_errors:
                        st.error("Imported dashboard could not be read correctly.")
                        for error in validation_errors:
                            st.warning(error)
                        return
                    new_configs = [*st.session_state["saved_configs"], imported]
                    if _persist_configs_with_feedback(
                        new_configs,
                        success_message="Imported dashboard.",
                    ):
                        st.session_state["last_imported_json_signature"] = (
                            upload_signature
                        )
                        st.rerun()
            except Exception as exc:
                st.error(f"Import failed: {exc}")


def render_dashboard_plot_editor(
    sel: dict,
    configs: list[dict],
    dataset: MainDatasetContext,
) -> None:
    """Render plot-level edit and removal controls for one dashboard."""
    plots = [plot for plot in (sel.get("plots") or []) if isinstance(plot, dict)]
    st.markdown("##### Edit Plot In Dashboard")
    if not plots:
        st.info("This dashboard contains no editable plots.")
        return

    plot_options = [plot.get("id") for plot in plots if plot.get("id")]
    plot_by_id = {plot.get("id"): plot for plot in plots if plot.get("id")}
    selected_plot_id = st.selectbox(
        "Select plot",
        options=plot_options,
        format_func=lambda value: _format_plot_option(plot_by_id.get(value)),
    )
    selected_plot = plot_by_id.get(selected_plot_id)
    if selected_plot is None:
        st.warning("Could not load the selected plot.")
        return

    top_left, top_right = st.columns([1.7, 1], vertical_alignment="bottom")
    with top_left:
        st.caption(
            f"Editing plot inside dashboard `{sel.get('name', 'Unnamed')}`."
        )
    with top_right:
        remove_disabled = len(plots) <= 1
        if st.button(
            "Remove selected plot",
            type="secondary",
            width="stretch",
            disabled=remove_disabled,
        ):
            updated_dashboard = remove_dashboard_plot(sel, selected_plot_id)
            new_configs = [
                updated_dashboard if cfg.get("id") == sel.get("id") else cfg
                for cfg in configs
            ]
            if _persist_configs_with_feedback(
                new_configs,
                success_message="Plot removed from dashboard.",
            ):
                st.rerun()
        if remove_disabled:
            st.caption("A dashboard must keep at least one plot.")

    editable_df = dataset.df_parsed
    editable_cols = dataset.cols
    plot_form_key = f"dashboard_plot_editor_{selected_plot_id}"
    initial_y2_cols = [
        col for col in (selected_plot.get("y2_cols") or []) if col in editable_cols
    ]
    initial_y_cols = [
        col for col in (selected_plot.get("y_cols") or []) if col in editable_cols
    ]
    x_default = (
        selected_plot.get("x_col")
        if selected_plot.get("x_col") in editable_cols
        else (dataset.date_col if dataset.date_col in editable_cols else editable_cols[0])
    )

    with st.expander("Plot settings", expanded=True):
        left, right = st.columns(2, vertical_alignment="top")
        with left:
            plot_label = st.text_input(
                "Plot label",
                value=selected_plot.get("title") or "",
                key=f"{plot_form_key}_title",
            )
            x_col = st.selectbox(
                "X axis",
                options=editable_cols,
                index=editable_cols.index(x_default),
                key=f"{plot_form_key}_x",
            )
            y_cols = st.multiselect(
                "Y axis (primary)",
                options=editable_cols,
                default=initial_y_cols,
                key=f"{plot_form_key}_y",
            )
            enable_y2 = st.toggle(
                "Enable secondary Y axis",
                value=bool(initial_y2_cols),
                key=f"{plot_form_key}_enable_y2",
            )
            y2_cols = (
                st.multiselect(
                    "Y axis (secondary)",
                    options=[col for col in editable_cols if col not in y_cols],
                    default=[col for col in initial_y2_cols if col not in y_cols],
                    key=f"{plot_form_key}_y2",
                )
                if enable_y2
                else []
            )
            plot_type = st.selectbox(
                "Type",
                options=PLOT_TYPES,
                index=(
                    PLOT_TYPES.index(selected_plot.get("plot_type"))
                    if selected_plot.get("plot_type") in PLOT_TYPES
                    else 0
                ),
                key=f"{plot_form_key}_type",
            )
        with right:
            theme_value = selected_plot.get("template", "plotly_white")
            if theme_value not in TEMPLATES:
                theme_value = "plotly_white"
            theme = st.selectbox(
                "Theme",
                options=TEMPLATES,
                index=TEMPLATES.index(theme_value),
                key=f"{plot_form_key}_theme",
            )
            yaxis_title_1 = st.text_input(
                "Y1 axis title",
                value=selected_plot.get("yaxis_title_1") or "",
                key=f"{plot_form_key}_y1_title",
            )
            yaxis_title_2 = st.text_input(
                "Y2 axis title",
                value=selected_plot.get("yaxis_title_2") or "",
                key=f"{plot_form_key}_y2_title",
                disabled=not enable_y2,
            )
            color_default = selected_plot.get("color_col")
            color_options = [None] + editable_cols
            color_index = (
                color_options.index(color_default)
                if color_default in color_options
                else 0
            )
            color_col = st.selectbox(
                "Color/group by (optional)",
                options=color_options,
                index=color_index,
                key=f"{plot_form_key}_color",
            )
            agg_default = selected_plot.get("agg")
            agg_options = [None, "mean", "sum", "min", "max", "median"]
            agg = st.selectbox(
                "Aggregate Y by X",
                options=agg_options,
                index=agg_options.index(agg_default) if agg_default in agg_options else 0,
                key=f"{plot_form_key}_agg",
            )

    style_map = render_plot_style_editor(
        selected_plot=selected_plot,
        y_cols=y_cols,
        y2_cols=y2_cols,
        key_prefix=plot_form_key,
    )
    preview_spec = build_plot_spec_from_builder(
        title=plot_label.strip() or None,
        x_col=x_col,
        y_cols=y_cols,
        plot_type=plot_type,
        template=theme,
        enable_secondary_axis=enable_y2,
        y2_cols=y2_cols,
        yaxis_title_1=yaxis_title_1.strip() or None,
        yaxis_title_2=yaxis_title_2.strip() or None,
        color_col=color_col,
        agg=agg,
        series_style=style_map,
    )
    preview_spec["id"] = selected_plot.get("id")

    st.markdown("##### Plot Preview")
    preview_fig, preview_warnings = render_plot_from_spec(
        editable_df,
        preview_spec,
        list(editable_df.columns),
    )
    if preview_warnings:
        for warning in preview_warnings:
            if warning.startswith("Matched "):
                st.info(warning)
            else:
                st.warning(warning)
    if preview_fig is not None:
        st.plotly_chart(
            preview_fig,
            width="stretch",
            key=f"{plot_form_key}_preview",
        )
    else:
        st.error("Could not render the edited plot on the current dataset.")

    if st.button("Save plot changes", width="stretch"):
        updated_dashboard = update_dashboard_plot(sel, selected_plot_id, preview_spec)
        validation_errors = validate_saved_config(updated_dashboard)
        if validation_errors:
            st.error("The updated dashboard is structurally invalid.")
            for error in validation_errors:
                st.warning(error)
            return

        new_configs = [
            updated_dashboard if cfg.get("id") == sel.get("id") else cfg
            for cfg in configs
        ]
        if _persist_configs_with_feedback(
            new_configs,
            success_message="Plot updated in dashboard.",
        ):
            st.rerun()


def render_plot_style_editor(
    *,
    selected_plot: dict,
    y_cols: list[str],
    y2_cols: list[str],
    key_prefix: str,
) -> dict[str, dict[str, object]]:
    """Render per-series style controls in the manager tab."""
    with st.expander("Series styling", expanded=False):
        st.caption("Adjust line color, width, and dash style for each visible series.")
        dash_options = [
            "solid",
            "dash",
            "dot",
            "dashdot",
            "longdash",
            "longdashdot",
        ]
        existing_style_map = selected_plot.get("series_style") or {}
        style_map: dict[str, dict[str, object]] = {}
        series_list = list(dict.fromkeys((y_cols or []) + (y2_cols or [])))
        if not series_list:
            st.info("Select Y columns to edit series styles.")
            return style_map

        for idx, series_name in enumerate(series_list):
            default_style = existing_style_map.get(series_name, {})
            default_color = default_style.get("color") or ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"][idx % 6]
            default_width = int(default_style.get("width") or 2)
            default_dash = default_style.get("dash") or "solid"
            safe = normalize_colname(series_name).replace(" ", "_") or "series"
            st.markdown(f"**{series_name}**")
            c1, c2, c3 = st.columns([1.2, 1, 1], vertical_alignment="center")
            with c1:
                color = st.color_picker(
                    "Color",
                    value=default_color,
                    key=f"{key_prefix}_{safe}_color",
                    label_visibility="collapsed",
                )
            with c2:
                width = st.slider(
                    "Width",
                    min_value=1,
                    max_value=8,
                    value=default_width,
                    key=f"{key_prefix}_{safe}_width",
                    label_visibility="collapsed",
                )
            with c3:
                dash = st.selectbox(
                    "Style",
                    options=dash_options,
                    index=dash_options.index(default_dash)
                    if default_dash in dash_options
                    else 0,
                    key=f"{key_prefix}_{safe}_dash",
                    label_visibility="collapsed",
                )
            style_map[series_name] = {
                "color": color,
                "width": width,
                "dash": dash,
            }
        return style_map


def _format_plot_option(plot: dict | None) -> str:
    """Build a compact label for a plot selector."""
    if not plot:
        return "Unnamed plot"
    title = plot.get("title") or "Untitled"
    series_count = len(plot.get("y_cols") or []) + len(plot.get("y2_cols") or [])
    return f"{title} ({series_count} series)"
