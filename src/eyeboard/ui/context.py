"""Shared UI dataclasses passed between Streamlit renderers."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from eyeboard.models import CsvReadReport, DateSettings, ReadOptions
from eyeboard.services.dataset import DataSource


@dataclass(slots=True)
class SidebarSelection:
    """Current data source and read options selected in the sidebar."""

    uploaded_file: Any
    recent_csv_id: str | None
    read_options: ReadOptions
    status_slot: Any  # sidebar container filled once the file is loaded


@dataclass(slots=True)
class MainDatasetContext:
    """Derived dataset state shared across the main tabs."""

    df: pd.DataFrame
    df_parsed: pd.DataFrame
    source: DataSource
    read_options: ReadOptions
    date_settings: DateSettings
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
