"""Numeric conversion of text columns, with an account of what could not be read."""

import re
from dataclasses import dataclass

import pandas as pd
from pandas.api.types import is_numeric_dtype

# A text column is treated as numeric when at least this share of its non-empty
# values can be read as numbers. The rest are ignored (and reported).
NUMERIC_THRESHOLD = 0.9
_EXAMPLE_LIMIT = 3
_DECIMAL_COMMA = re.compile(r"^\s*-?\d+,\d+\s*$")


@dataclass(frozen=True, slots=True)
class NumericConversion:
    """Outcome of trying to read one column as numbers."""

    is_numeric: bool
    invalid_count: int = 0
    invalid_examples: tuple[str, ...] = ()
    looks_like_decimal_comma: bool = False


def _decimal_comma_share(values: pd.Series) -> float:
    """Share of the values that look like numbers written with a decimal comma."""
    if values.empty:
        return 0.0
    return float(values.astype(str).str.match(_DECIMAL_COMMA).mean())


def coerce_numeric(series: pd.Series) -> tuple[pd.Series, NumericConversion]:
    """Read a column as numbers where that is reasonable.

    Numeric columns are returned untouched. A text column becomes numeric when
    at least ``NUMERIC_THRESHOLD`` of its non-empty values convert; the values
    that do not are set to missing and described in the result. Otherwise the
    column is returned unchanged and flagged as not numeric.
    """
    if is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return series, NumericConversion(is_numeric=True)
    if not (
        pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
    ):
        return series, NumericConversion(is_numeric=False)

    text = series.astype("string").str.strip()
    filled = series.notna() & text.ne("")
    filled_count = int(filled.sum())
    if filled_count == 0:
        return series, NumericConversion(is_numeric=False)

    converted = pd.to_numeric(series, errors="coerce")
    invalid = filled & converted.isna()
    invalid_count = int(invalid.sum())
    comma_share = _decimal_comma_share(
        series[invalid] if invalid_count else series[filled]
    )

    if (filled_count - invalid_count) / filled_count < NUMERIC_THRESHOLD:
        return series, NumericConversion(
            is_numeric=False,
            invalid_count=invalid_count,
            looks_like_decimal_comma=comma_share >= 0.5,
        )

    examples = tuple(
        str(value) for value in series[invalid].drop_duplicates().head(_EXAMPLE_LIMIT)
    )
    return converted, NumericConversion(
        is_numeric=True,
        invalid_count=invalid_count,
        invalid_examples=examples,
        looks_like_decimal_comma=invalid_count > 0 and comma_share >= 0.5,
    )
