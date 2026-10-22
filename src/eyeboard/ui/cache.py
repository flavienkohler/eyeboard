"""Streamlit caches for loading and parsing tables.

This is the only module that knows about ``st.cache_data``. Keys are cheap
descriptions of the inputs (source key, options); the large inputs themselves
(``_source``, ``_df``) are prefixed with an underscore so Streamlit does not hash
them. ``cache_data`` returns a copy on every call, so cached tables can never be
changed by accident. The language is part of every key because the cached results
contain messages (warnings, checks) written in the language of the session.
"""

import pandas as pd
import streamlit as st

from eyeboard.i18n import current_language, t
from eyeboard.models import CsvReadReport, DateSettings, ReadOptions
from eyeboard.services.csv_reading import CsvReadError
from eyeboard.services.dataset import (
    DataSource,
    ParsedTable,
    load_table,
    parse_table,
)
from eyeboard.services.profile import ColumnProfile, profile_columns

MAX_CACHED_TABLES = 6


@st.cache_data(show_spinner=False, max_entries=MAX_CACHED_TABLES)
def _load_table_cached(
    source_key: str,
    label: str,
    kind: str,
    options: ReadOptions,
    language: str,
    _source: DataSource,
) -> tuple[pd.DataFrame, CsvReadReport]:
    return load_table(_source, options)


@st.cache_data(show_spinner=False, max_entries=MAX_CACHED_TABLES)
def _parse_table_cached(
    source_key: str,
    options: ReadOptions,
    settings: DateSettings,
    language: str,
    _df: pd.DataFrame,
) -> ParsedTable:
    return parse_table(_df, settings)


def load_table_cached(
    source: DataSource,
    options: ReadOptions,
) -> tuple[pd.DataFrame | None, CsvReadReport | None, str | None]:
    """Load a source (cached). Returns ``(table, report, error_message)``."""
    try:
        df, report = _load_table_cached(
            source.key, source.label, source.kind, options, current_language(), source
        )
    except CsvReadError as exc:
        return None, None, str(exc)
    except OSError as exc:
        return None, None, t("The file could not be opened: {error}", error=exc)
    return df, report, None


def parse_table_cached(
    source: DataSource,
    options: ReadOptions,
    settings: DateSettings,
    df: pd.DataFrame,
) -> ParsedTable:
    """Parse the date column of a loaded table (cached)."""
    return _parse_table_cached(source.key, options, settings, current_language(), df)


@st.cache_data(show_spinner=False, max_entries=MAX_CACHED_TABLES)
def _profile_table_cached(
    source_key: str,
    options: ReadOptions,
    settings: DateSettings,
    language: str,
    _df: pd.DataFrame,
) -> list[ColumnProfile]:
    return profile_columns(_df)


def profile_table_cached(
    source: DataSource,
    options: ReadOptions,
    settings: DateSettings,
    parsed_df: pd.DataFrame,
) -> list[ColumnProfile]:
    """Profile the columns of a parsed table (cached)."""
    return _profile_table_cached(
        source.key, options, settings, current_language(), parsed_df
    )
