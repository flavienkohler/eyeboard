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
