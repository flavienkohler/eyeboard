"""Shared application dataclasses."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class CsvReadReport:
    """Summary of how a CSV input was interpreted during loading."""

    source_kind: str
    source_label: str
    row_count: int
    column_count: int
    separator_label: str
    separator_auto_detected: bool
    decimal_label: str
    header_label: str
    warnings: list[str] = field(default_factory=list)
    encoding_label: str = "UTF-8"


@dataclass(frozen=True, slots=True)
class ReadOptions:
    """How to turn the bytes of a CSV file into a table (hashable: used as a cache key)."""

    sep: str | None = None
    decimal: str = "."
    header: int | tuple[int, ...] | None = 0
    skiprows: tuple[int, ...] | None = None
    encoding: str | None = None


@dataclass(frozen=True, slots=True)
class DateSettings:
    """How to read the date column of a table (hashable: used as a cache key)."""

    column: str | None = None
    mode: str = "Auto-detect"
    format: str | None = None
