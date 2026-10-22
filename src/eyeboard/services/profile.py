"""Per-column profile of a table: type, gaps, distinct values, range and checks.

Pure functions of a table, so the interface can cache them by file.
"""

from dataclasses import dataclass

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from eyeboard.i18n import t
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
    constant: bool = False  # one value only
    empty: bool = False  # no value at all
    index_like: bool = False  # 1, 2, 3...: a row counter, not a measurement


def _range(series: pd.Series, kind: str) -> tuple[str, str]:
    """Format the smallest and largest value of a number or date column."""
    values = series.dropna()
    if values.empty or kind == "text":
        return "", ""
    if kind == "date":
        return str(values.min()), str(values.max())
    return f"{values.min():.6g}", f"{values.max():.6g}"


def _is_row_counter(numbers: pd.Series) -> bool:
    """Whole numbers that only go up, never repeat and have no gap in the data."""
    if len(numbers) < 3 or numbers.isna().any():
        return False
    return bool(
        numbers.is_monotonic_increasing
        and numbers.is_unique
        and (numbers % 1 == 0).all()
    )


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
                    t(
                        "{count:,} value(s) are not numbers ({examples})",
                        count=conversion.invalid_count,
                        examples=examples,
                    )
                )
        else:
            kind = "text"
        if conversion.looks_like_decimal_comma:
            decimal_comma = True
            checks.append(t("numbers with a decimal comma: set Decimal to Comma"))

    missing = int(series.isna().sum())
    distinct = int(series.nunique(dropna=True))
    empty = missing == len(series) and len(series) > 0
    constant = distinct == 1 and not empty
    if empty:
        checks.append(t("empty"))
    elif constant:
        checks.append(t("constant"))

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
        constant=constant,
        empty=empty,
        index_like=kind == "number" and _is_row_counter(numbers),
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


def suggested_series(profiles: list[ColumnProfile]) -> list[str]:
    """The column a first plot should show: the first real measurement.

    Row counters, constant and empty columns make dull first plots, so they come
    last; when nothing else is numeric the first number is used anyway.
    """
    numbers = [p for p in profiles if p.kind == "number"]
    good = [p for p in numbers if not (p.index_like or p.constant or p.empty)]
    chosen = (good or numbers)[:1]
    return [p.name for p in chosen]
