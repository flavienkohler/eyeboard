"""From a data source to a table: loading and date parsing, without any UI code.

Everything here is a pure function of its inputs, so the results can be cached
by the interface and tested without Streamlit.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from eyeboard.models import CsvReadReport, DateSettings, ReadOptions
from eyeboard.services.csv_reading import read_csv_bytes
from eyeboard.services.date_parsing import parse_dates_flexible

# Share of successfully parsed dates under which the user is warned.
DATE_PARSE_WARNING_THRESHOLD = 0.8


@dataclass(frozen=True, slots=True)
class DataSource:
    """Where the bytes of a CSV come from.

    ``key`` identifies the content cheaply (it changes when the content may have
    changed), so callers can cache on it without reading or hashing the bytes.
    ``read_bytes`` is only called when the content is really needed.
    """

    key: str
    label: str
    kind: str
    read_bytes: Callable[[], bytes]


def source_from_upload(uploaded_file: Any) -> DataSource:
    """Describe a file uploaded through Streamlit (``file_id`` is unique per upload)."""
    return DataSource(
        key=f"upload:{uploaded_file.file_id}",
        label=uploaded_file.name,
        kind="Upload",
        read_bytes=uploaded_file.getvalue,
    )


def source_from_path(
    path: str | Path,
    *,
    kind: str = "Server path",
    label: str | None = None,
) -> DataSource:
    """Describe a file on disk; its size and modification time are part of the key."""
    file_path = Path(path)
    stat = file_path.stat()
    return DataSource(
        key=f"path:{file_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}",
        label=label or file_path.name,
        kind=kind,
        read_bytes=file_path.read_bytes,
    )


def load_table(
    source: DataSource,
    options: ReadOptions,
) -> tuple[pd.DataFrame, CsvReadReport]:
    """Read a source into a cleaned table and its report.

    Raises ``CsvReadError`` (readable message) or ``OSError`` (file problems).
    """
    header = (
        list(options.header) if isinstance(options.header, tuple) else options.header
    )
    return read_csv_bytes(
        source.read_bytes(),
        decimal=options.decimal,
        sep=options.sep,
        header=header,
        skiprows=list(options.skiprows) if options.skiprows else None,
        encoding=options.encoding,
        source_kind=source.kind,
        source_label=source.label,
    )


@dataclass(slots=True)
class ParsedTable:
    """A table whose date column has been parsed, with a summary of how it went."""

    df: pd.DataFrame
    date_parse_success_count: int = 0
    date_parse_candidate_count: int = 0
    date_parse_warning: str | None = None


def summarize_date_parsing(
    df: pd.DataFrame,
    df_parsed: pd.DataFrame,
    date_col: str | None,
) -> tuple[int, int, str | None]:
    """Count how many non-empty values of the date column were parsed."""
    if (
        date_col is None
        or date_col not in df.columns
        or date_col not in df_parsed.columns
    ):
        return 0, 0, None

    source_series = df[date_col]
    candidate_mask = source_series.notna()
    if pd.api.types.is_object_dtype(source_series) or pd.api.types.is_string_dtype(
        source_series
    ):
        stripped = source_series.astype("string").str.strip()
        candidate_mask = candidate_mask & stripped.ne("")

    candidate_count = int(candidate_mask.sum())
    success_count = int(df_parsed[date_col][candidate_mask].notna().sum())
    if candidate_count == 0:
        return success_count, candidate_count, None

    warning = None
    if success_count / candidate_count < DATE_PARSE_WARNING_THRESHOLD:
        warning = (
            f"Only {success_count:,} of {candidate_count:,} non-empty date values "
            "parsed successfully."
        )
    return success_count, candidate_count, warning


def parse_table(df: pd.DataFrame, settings: DateSettings) -> ParsedTable:
    """Parse the date column of a table according to the date settings."""
    parsed = parse_dates_flexible(
        df,
        settings.column,
        date_mode=settings.mode,
        date_format=settings.format,
    )
    success, candidates, warning = summarize_date_parsing(df, parsed, settings.column)
    return ParsedTable(parsed, success, candidates, warning)
