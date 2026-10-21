"""CSV parsing and loading helpers."""

import io
import logging
import re
from collections.abc import Sequence

import pandas as pd
from pandas.api.types import is_object_dtype

from eyeboard.config import CANDIDATE_SEPARATORS, ENCODING_OPTIONS
from eyeboard.models import CsvReadReport

LOGGER = logging.getLogger(__name__)

SNIFF_CHARS = 30_000
_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_RENAMED_DUPLICATE = re.compile(r"^(?P<base>.+)\.\d+$")


class CsvReadError(Exception):
    """A CSV could not be read; the message is meant to be shown to the user."""


def _separator_label(sep: str | None) -> str:
    """Convert a separator character into a display label."""
    return {
        ",": "Comma (,)",
        ";": "Semicolon (;)",
        "\t": "Tab (\\t)",
        "|": "Pipe (|)",
    }.get(sep, "Auto-detect")


def _decimal_label(decimal: str) -> str:
    """Convert a decimal character into a display label."""
    return "Comma (,)" if decimal == "," else "Dot (.)"


def _header_label(
    header: int | Sequence[int] | None,
    skiprows: Sequence[int] | None,
) -> str:
    """Describe the configured header mode for display."""
    if header is None:
        return "No header"

    if isinstance(header, Sequence) and not isinstance(header, str):
        if list(header) == [0, 1]:
            return "Two rows (multi header)"

    if header == 0 and list(skiprows or []) == [0]:
        return "Second row (skip first)"

    return "First row"


def _build_read_report(
    *,
    source_kind: str,
    source_label: str,
    df: pd.DataFrame,
    decimal: str,
    sep: str | None,
    inferred_sep: str | None,
    header: int | Sequence[int] | None,
    skiprows: Sequence[int] | None,
    encoding_label: str,
    warnings: list[str],
) -> CsvReadReport:
    """Create a compact summary of the read settings used for a CSV."""
    warnings = list(warnings)
    separator_auto_detected = sep is None

    if sep is not None:
        separator_label = _separator_label(sep)
    elif inferred_sep is not None:
        separator_label = f"Auto-detected {_separator_label(inferred_sep)}"
    else:
        separator_label = "Comma (,) (assumed)"
        warnings.append(
            "No separator could be detected; a comma was assumed. "
            "Choose one in Reading options if the columns look wrong."
        )

    return CsvReadReport(
        source_kind=source_kind,
        source_label=source_label,
        row_count=len(df),
        column_count=len(df.columns),
        separator_label=separator_label,
        separator_auto_detected=separator_auto_detected,
        decimal_label=_decimal_label(decimal),
        header_label=_header_label(header, skiprows),
        warnings=warnings,
        encoding_label=encoding_label,
    )


def detect_separator_from_sample(sample: str, decimal: str = ".") -> str | None:
    """Heuristically detect the field separator from a text sample."""
    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return None

    best_sep: str | None = None
    best_score = 0.0

    for sep in CANDIDATE_SEPARATORS:
        if sep == decimal:
            continue
        counts = [line.count(sep) for line in lines[:25]]
        if not counts or max(counts) == 0:
            continue

        mean_count = sum(counts) / len(counts)
        variance = sum((count - mean_count) ** 2 for count in counts) / len(counts)
        score = mean_count - variance
        if score > best_score:
            best_score = score
            best_sep = sep

    return best_sep


def decode_csv_bytes(
    raw: bytes,
    encoding: str | None = None,
) -> tuple[str, str, list[str]]:
    """Decode CSV bytes once and return ``(text, encoding_label, warnings)``.

    With ``encoding=None`` the encoding is detected: a byte-order mark wins, then
    strict UTF-8, then Windows-1252 (what Excel writes in Western locales) and
    finally Latin-1, which can decode any byte. A UTF-8 byte-order mark is
    stripped so it never ends up in the first column name.
    """
    if encoding is not None:
        text = raw.decode("utf-8-sig" if encoding == "utf-8" else encoding)
        return text, _encoding_label(encoding), []

    if raw.startswith(_UTF16_BOMS):
        return raw.decode("utf-16"), "UTF-16", []
    if raw.startswith(_UTF8_BOM):
        return raw.decode("utf-8-sig"), "UTF-8", []

    try:
        return raw.decode("utf-8"), "UTF-8", []
    except UnicodeDecodeError:
        pass

    for fallback in ("cp1252", "latin-1"):
        try:
            text = raw.decode(fallback)
        except UnicodeDecodeError:
            continue
        label = _encoding_label(fallback)
        return text, label, [f"The file is not valid UTF-8; it was decoded as {label}."]

    raise CsvReadError("The file could not be decoded.")  # pragma: no cover


def _encoding_label(codec: str) -> str:
    """Return the display label of a codec name."""
    for label, known_codec in ENCODING_OPTIONS.items():
        if known_codec == codec:
            return label.split(" (")[0]
    return {"latin-1": "Latin-1"}.get(codec, codec)


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns if present."""
    if isinstance(df.columns, pd.MultiIndex):
        flattened = df.copy()
        flattened.columns = [
            " | ".join(str(value) for value in column if str(value) != "nan").strip()
            for column in df.columns
        ]
        return flattened
    return df


def strip_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace from string-like dataframe columns."""
    stripped = df.copy()
    for col in stripped.columns:
        if col in stripped and is_object_dtype(stripped[col]):
            stripped[col] = stripped[col].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    return stripped


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and stray byte-order marks from string column names."""
    cleaned = df.copy()
    cleaned.columns = [
        name.replace("﻿", "").strip() if isinstance(name, str) else name
        for name in df.columns
    ]
    return cleaned


def drop_empty_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop columns without any value and return the frame and the dropped count."""
    non_empty = df.dropna(axis=1, how="all")
    return non_empty, len(df.columns) - len(non_empty.columns)


def find_renamed_duplicates(columns: Sequence[object]) -> list[str]:
    """Return column names that pandas renamed because they were duplicated."""
    names = {name for name in columns if isinstance(name, str)}
    renamed = []
    for name in columns:
        match = _RENAMED_DUPLICATE.match(name) if isinstance(name, str) else None
        if match and match.group("base") in names:
            renamed.append(name)
    return renamed


def read_csv_bytes(
    raw: bytes,
    *,
    decimal: str,
    sep: str | None,
    header: int | Sequence[int] | None,
    skiprows: Sequence[int] | None,
    encoding: str | None = None,
    source_kind: str = "Upload",
    source_label: str = "",
) -> tuple[pd.DataFrame, CsvReadReport]:
    """Read CSV bytes into a cleaned dataframe and a report.

    This is the pure core of the reader: the same bytes and options always give
    the same result, so it is easy to test (and to cache). Raises
    ``CsvReadError`` with a message meant for the user when the file cannot be
    read.
    """
    try:
        text, encoding_label, warnings = decode_csv_bytes(raw, encoding)
    except UnicodeDecodeError as exc:
        raise CsvReadError(
            "The file could not be decoded with the selected encoding. "
            "Try another one in Reading options."
        ) from exc

    if not text.strip():
        raise CsvReadError("The file is empty or has no columns to read.")

    inferred_sep = detect_separator_from_sample(text[:SNIFF_CHARS], decimal=decimal)
    # Single-column files have no separator to detect; a comma is then harmless.
    effective_sep = sep if sep is not None else (inferred_sep or ",")

    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=effective_sep,
            decimal=decimal,
            header=header,
            skiprows=skiprows,
            engine="c",
        )
    except pd.errors.EmptyDataError as exc:
        raise CsvReadError("The file is empty or has no columns to read.") from exc
    except (pd.errors.ParserError, ValueError) as exc:
        raise CsvReadError(
            "The file could not be parsed with the current separator, header or "
            f"decimal settings. Details: {exc}"
        ) from exc

    cleaned = flatten_columns(df)
    cleaned = clean_column_names(cleaned)
    cleaned, dropped_count = drop_empty_columns(cleaned)
    cleaned = strip_object_columns(cleaned)

    if dropped_count:
        warnings.append(f"Dropped {dropped_count} empty column(s).")
    renamed = find_renamed_duplicates(list(cleaned.columns))
    if renamed:
        warnings.append(
            "Duplicate column names were renamed: " + ", ".join(sorted(renamed)) + "."
        )

    report = _build_read_report(
        source_kind=source_kind,
        source_label=source_label,
        df=cleaned,
        decimal=decimal,
        sep=sep,
        inferred_sep=inferred_sep,
        header=header,
        skiprows=skiprows,
        encoding_label=encoding_label,
        warnings=warnings,
    )
    return cleaned, report
