"""Date parsing and date-order inference helpers."""

import re
import warnings

import pandas as pd

DATE_ORDER_PATTERN = re.compile(
    r"^\s*(?P<first>\d{1,4})[./-](?P<second>\d{1,2})[./-](?P<third>\d{1,4})(?:\D|$)"
)


def sample_date_values(series: pd.Series, limit: int = 50) -> list[str]:
    """Collect distinct non-empty date-like string samples from a series."""
    samples: list[str] = []
    seen: set[str] = set()
    for value in series.dropna():
        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none"}:
            continue
        if text in seen:
            continue
        seen.add(text)
        samples.append(text)
        if len(samples) >= limit:
            break
    return samples


def infer_dayfirst_from_series(series: pd.Series) -> bool | None:
    """Infer day/month ordering from date-like values when the signal is strong."""
    dayfirst_votes = 0
    monthfirst_votes = 0
    dotted_ambiguous = 0

    for text in sample_date_values(series):
        match = DATE_ORDER_PATTERN.match(text)
        if not match:
            continue

        first_token = match.group("first")
        if len(first_token) == 4:
            continue

        first_num = int(first_token)
        second_num = int(match.group("second"))

        if first_num > 12 and second_num <= 12:
            dayfirst_votes += 1
        elif second_num > 12 and first_num <= 12:
            monthfirst_votes += 1
        elif "." in text and first_num <= 12 and second_num <= 12:
            dotted_ambiguous += 1

    if dayfirst_votes > monthfirst_votes:
        return True
    if monthfirst_votes > dayfirst_votes:
        return False
    if dotted_ambiguous > 0:
        return True
    return None


def to_datetime_safely(series: pd.Series, **kwargs) -> pd.Series:
    """Parse datetimes while suppressing pandas warning noise during inference."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(series, errors="coerce", **kwargs)


def parse_date_series(
    series: pd.Series,
    *,
    date_mode: str = "Auto-detect",
    date_format: str | None = None,
) -> pd.Series:
    """Parse a date series with auto-detection and optional manual override."""
    if date_format:
        return to_datetime_safely(series, format=date_format)

    if date_mode == "Day-first":
        return to_datetime_safely(series, dayfirst=True)
    if date_mode == "Month-first":
        return to_datetime_safely(series, dayfirst=False)

    inferred_dayfirst = infer_dayfirst_from_series(series)
    candidate_orders = (
        [inferred_dayfirst, not inferred_dayfirst]
        if inferred_dayfirst is not None
        else [False, True]
    )

    best_parsed: pd.Series | None = None
    best_score = -1.0
    best_dayfirst: bool | None = None

    for candidate_dayfirst in candidate_orders:
        parsed = to_datetime_safely(series, dayfirst=candidate_dayfirst)
        score = float(parsed.notna().mean())
        if score > best_score:
            best_parsed = parsed
            best_score = score
            best_dayfirst = candidate_dayfirst
            continue

        if (
            abs(score - best_score) < 1e-9
            and inferred_dayfirst is not None
            and candidate_dayfirst == inferred_dayfirst
            and best_dayfirst != inferred_dayfirst
        ):
            best_parsed = parsed
            best_dayfirst = candidate_dayfirst

    if best_parsed is not None:
        return best_parsed
    return to_datetime_safely(series)


def parse_dates_flexible(
    df: pd.DataFrame,
    date_col: str | None,
    *,
    date_mode: str = "Auto-detect",
    date_format: str | None = None,
) -> pd.DataFrame:
    """Parse a dataframe date column with auto-detection and manual overrides."""
    if date_col is None or date_col not in df.columns:
        return df

    parsed_df = df.copy()
    try:
        parsed_df[date_col] = parse_date_series(
            parsed_df[date_col],
            date_mode=date_mode,
            date_format=date_format,
        )
    except Exception:
        parsed_df[date_col] = to_datetime_safely(parsed_df[date_col])
    return parsed_df
