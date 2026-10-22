"""Choosing a data source: a recent file, or a file uploaded just now."""

import streamlit as st

from eyeboard.services.dataset import DataSource, source_from_path, source_from_upload
from eyeboard.services.demo import DEMO_LABELS, demo_source
from eyeboard.services.recent_csvs import (
    format_recent_csv_details,
    get_recent_csv_cache_path,
    get_recent_csv_entry,
    list_recent_csvs,
)

RECENT_CHOICES = 10
DEMO_PREFIX = "demo:"  # ids of the generated demo files in the picker


def source_for_recent(entry_id: str) -> DataSource | None:
    """The data source of a recent file, or ``None`` when it is gone."""
    entry = get_recent_csv_entry(entry_id)
    cache_path = get_recent_csv_cache_path(entry_id)
    if entry is None or not cache_path.exists():
        return None
    return source_from_path(
        cache_path,
        kind="Recent cache",
        label=entry.get("filename") or cache_path.name,
    )


def render_source_picker(label: str, key: str) -> DataSource | None:
    """Offer an upload and the recent files; a chosen recent file wins."""
    recent = {e["id"]: e for e in list_recent_csvs(RECENT_CHOICES) if e.get("id")}
    demo = {f"{DEMO_PREFIX}{name}": text for name, text in DEMO_LABELS.items()}

    def describe(value: str | None) -> str:
        if value is None:
            return "Choose a recent file or a demo file"
        if value in demo:
            return demo[value]
        return recent[value].get("filename", "Unnamed CSV")

    chosen = st.selectbox(
        f"File for {label}",
        [None, *recent, *demo],
        format_func=describe,
        key=f"{key}_recent",
    )
    if chosen in demo:
        return demo_source(chosen.removeprefix(DEMO_PREFIX))
    if chosen is not None:
        st.caption(format_recent_csv_details(recent[chosen]))
        source = source_for_recent(chosen)
        if source is not None:
            return source
        st.warning("This recent file is no longer available.")

    uploaded = st.file_uploader(
        f"or upload a file for {label}", type=["csv"], key=f"{key}_upload"
    )
    return source_from_upload(uploaded) if uploaded is not None else None
