"""Column name normalization and matching helpers."""

import difflib
from collections.abc import Sequence

from plot_studio.config import DATE_KEYWORDS


def normalize_colname(name: str | None) -> str:
    """Normalize a column name for fuzzy matching."""
    if name is None:
        return ""
    normalized = str(name).strip().lower()
    normalized = normalized.replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def resolve_column(requested: str | None, available_cols: Sequence[str]) -> str | None:
    """Resolve a requested column to the closest available column."""
    if not requested:
        return None
    if requested in available_cols:
        return requested

    norm_to_actual = {normalize_colname(column): column for column in available_cols}
    requested_normalized = normalize_colname(requested)

    if requested_normalized in norm_to_actual:
        return norm_to_actual[requested_normalized]

    candidates = difflib.get_close_matches(
        requested_normalized,
        list(norm_to_actual.keys()),
        n=1,
        cutoff=0.80,
    )
    if candidates:
        return norm_to_actual[candidates[0]]
    return None


def guess_date_column(columns: Sequence[str]) -> str | None:
    """Guess a date/time column based on common keywords."""
    for column in columns:
        normalized = normalize_colname(column)
        if any(keyword in normalized for keyword in DATE_KEYWORDS):
            return str(column)
    return None
