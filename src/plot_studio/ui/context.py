"""Shared UI dataclasses passed between Streamlit renderers."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from plot_studio.models import CsvReadReport


@dataclass(slots=True)
class ReadingOptions:
    """Parsed CSV and date-reading options from the sidebar."""

    sep: str | None
    decimal: str
    header: int | list[int] | None
    skiprows: list[int] | None
    date_mode: str
    date_format: str | None


@dataclass(slots=True)
class SidebarSelection:
    """Current data source and read options selected in the sidebar."""

    uploaded_file: Any
    recent_csv_id: str | None
    reading_options: ReadingOptions


@dataclass(slots=True)
class MainDatasetContext:
    """Derived dataset state shared across the main tabs."""

    df: pd.DataFrame
    df_parsed: pd.DataFrame
    cols: list[str]
    date_col: str | None
    date_guess: str | None
    label: str
    read_report: CsvReadReport | None
    date_parse_success_count: int
    date_parse_candidate_count: int
    date_parse_mode: str
    date_format: str | None
    date_parse_warning: str | None
