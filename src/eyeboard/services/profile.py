"""Per-column profile of a table: type, gaps, distinct values, range and checks.

Pure functions of a table, so the interface can cache them by file.
"""

from dataclasses import dataclass

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from eyeboard.services.numeric import coerce_numeric


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """What can be said about one column at a glance."""

    name: str
    kind: str  # "number", "date" or "text"
    missing_count: int
    missing_share: float
    distinct: int
    minimum: str
    maximum: str
    checks: tuple[str, ...] = ()
    decimal_comma: bool = False


def _range(series: pd.Series, kind: str) -> tuple[str, str]:
    """Format the smallest and largest value of a number or date column."""
    values = series.dropna()
    if values.empty or kind == "text":
        return "", ""
    if kind == "date":
        return str(values.min()), str(values.max())
    return f"{values.min():.6g}", f"{values.max():.6g}"


def profile_column(name: str, series: pd.Series) -> ColumnProfile:
    """Profile one column; text that is mostly numbers is read as numbers."""
    checks: list[str] = []
    decimal_comma = False

    if is_datetime64_any_dtype(series):
        kind, numbers = "date", series
    elif is_numeric_dtype(series) and not is_bool_dtype(series):
        kind, numbers = "number", series
    else:
        numbers, conversion = coerce_numeric(series)
        if conversion.is_numeric:
            kind = "number"
            if conversion.invalid_count:
                examples = ", ".join(
                    f"'{text}'" for text in conversion.invalid_examples
                )
                checks.append(
                    f"{conversion.invalid_count:,} value(s) are not numbers ({examples})"
                )
        else:
            kind = "text"
        if conversion.looks_like_decimal_comma:
            decimal_comma = True
            checks.append("numbers with a decimal comma: set Decimal to Comma")

    missing = int(series.isna().sum())
    distinct = int(series.nunique(dropna=True))
    if missing == len(series) and len(series):
        checks.append("empty")
    elif distinct == 1:
        checks.append("constant")

    minimum, maximum = _range(numbers, kind)
    return ColumnProfile(
        name=str(name),
        kind=kind,
        missing_count=missing,
        missing_share=missing / len(series) if len(series) else 0.0,
        distinct=distinct,
        minimum=minimum,
        maximum=maximum,
        checks=tuple(checks),
        decimal_comma=decimal_comma,
    )


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """Profile every column of a table (the date column should already be parsed)."""
    return [profile_column(column, df[column]) for column in df.columns]


def profiles_to_frame(profiles: list[ColumnProfile]) -> pd.DataFrame:
    """Lay the profiles out as a table for display."""
    return pd.DataFrame(
        {
            "column": [p.name for p in profiles],
            "type": [p.kind for p in profiles],
            "missing %": [round(100 * p.missing_share, 1) for p in profiles],
            "distinct": [p.distinct for p in profiles],
            "min": [p.minimum for p in profiles],
            "max": [p.maximum for p in profiles],
            "checks": ["; ".join(p.checks) for p in profiles],
        }
    )
