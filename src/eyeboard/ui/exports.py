"""Download buttons for charts and tables."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from eyeboard.plotting.export import csv_bytes, file_stem, html_bytes


def render_downloads(
    *,
    toggle_key: str,
    name: str,
    fig: go.Figure | None = None,
    table: pd.DataFrame | None = None,
    table_label: str = "Data (CSV)",
) -> None:
    """Offer the chart as HTML and a table as CSV, built only when asked for.

    Building a standalone HTML page serialises every point, so the files are
    prepared only while the toggle is on, not on every rerun of the page.
    """
    if not st.toggle(
        "Prepare export files",
        key=toggle_key,
        help="PNG: use the camera icon in the chart's toolbar.",
    ):
        return
    stem = file_stem(name)
    columns = st.columns(2)
    if fig is not None:
        columns[0].download_button(
            "Chart (HTML)",
            data=html_bytes(fig),
            file_name=f"{stem}.html",
            mime="text/html",
            width="stretch",
            key=f"{toggle_key}_html",
        )
    if table is not None and not table.empty:
        columns[1].download_button(
            table_label,
            data=csv_bytes(table),
            file_name=f"{stem}.csv",
            mime="text/csv",
            width="stretch",
            key=f"{toggle_key}_csv",
        )
