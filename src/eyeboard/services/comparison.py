"""Compare one series of two datasets: align B on A, then measure the gap.

Pure functions of series, so they are tested with known numbers and used by the
interface without any Streamlit code.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

Alignment = Literal["timestamps", "elapsed"]


@dataclass(frozen=True, slots=True)
class SeriesComparison:
    """How B differs from A over the part of the x range both cover."""

    points: int
    rmse: float
    mae: float
    bias: float  # mean of (B - A): positive when B is above A
    correlation: float  # nan when it cannot be computed (constant series, one point)


def _clean(x: pd.Series, y: pd.Series) -> pd.DataFrame:
    """Sorted, duplicate-free (x, y) pairs without missing values."""
    frame = pd.DataFrame({"x": x.to_numpy(), "y": pd.to_numeric(y, errors="coerce")})
    frame = frame.dropna()
    return frame.groupby("x", sort=True, as_index=False)["y"].mean()


def _seconds(x: pd.Series, origin) -> np.ndarray:
    """Position on the x axis as a plain number: seconds for dates, else units."""
    if is_datetime64_any_dtype(x):
        return ((x - origin) / pd.Timedelta(seconds=1)).to_numpy(dtype=float)
    return (x - origin).to_numpy(dtype=float)


def is_comparable_axis(x: pd.Series) -> bool:
    """Whether x can be aligned: dates or numbers (not text categories)."""
    return is_datetime64_any_dtype(x) or (
        is_numeric_dtype(x) and not pd.api.types.is_bool_dtype(x)
    )


def compare_series(
    a_x: pd.Series,
    a_y: pd.Series,
    b_x: pd.Series,
    b_y: pd.Series,
    *,
    alignment: Alignment = "timestamps",
) -> SeriesComparison | None:
    """Compare B with A, or return ``None`` when there is nothing to compare.

    B is interpolated onto the x values of A, only inside the range both
    cover (nothing is extrapolated). With ``alignment="elapsed"`` each series
    first counts from its own start, to compare two runs begun at different times.
    ``None`` means: x is not dates or numbers, the kinds differ, or there is no overlap.
    """
    if not (is_comparable_axis(a_x) and is_comparable_axis(b_x)):
        return None
    if is_datetime64_any_dtype(a_x) != is_datetime64_any_dtype(b_x):
        return None

    a, b = _clean(a_x, a_y), _clean(b_x, b_y)
    if a.empty or b.empty:
        return None

    if alignment == "elapsed":
        a_origin, b_origin = a["x"].min(), b["x"].min()
    else:
        a_origin = b_origin = min(a["x"].min(), b["x"].min())
    a_pos, b_pos = _seconds(a["x"], a_origin), _seconds(b["x"], b_origin)

    low, high = max(a_pos[0], b_pos[0]), min(a_pos[-1], b_pos[-1])
    inside = (a_pos >= low) & (a_pos <= high)
    if low > high or not inside.any():
        return None

    a_values = a["y"].to_numpy(dtype=float)[inside]
    b_values = np.interp(a_pos[inside], b_pos, b["y"].to_numpy(dtype=float))
    gap = b_values - a_values

    correlation = float("nan")
    if len(gap) >= 2 and a_values.std() > 0 and b_values.std() > 0:
        correlation = float(np.corrcoef(a_values, b_values)[0, 1])
    return SeriesComparison(
        points=int(len(gap)),
        rmse=float(np.sqrt(np.mean(gap**2))),
        mae=float(np.mean(np.abs(gap))),
        bias=float(np.mean(gap)),
        correlation=correlation,
    )


def shift_to_start(b_x: pd.Series, a_x: pd.Series) -> pd.Series:
    """Move B along x so that it starts where A starts (for elapsed-time overlays).

    Dates and numbers only; anything else is returned unchanged.
    """
    if not (is_comparable_axis(a_x) and is_comparable_axis(b_x)):
        return b_x
    if is_datetime64_any_dtype(a_x) != is_datetime64_any_dtype(b_x):
        return b_x
    if a_x.dropna().empty or b_x.dropna().empty:
        return b_x
    return b_x + (a_x.min() - b_x.min())


def overlap(a_x: pd.Series, b_x: pd.Series) -> tuple[object, object] | None:
    """The x range both series cover, or ``None`` when they do not meet."""
    if not (is_comparable_axis(a_x) and is_comparable_axis(b_x)):
        return None
    if is_datetime64_any_dtype(a_x) != is_datetime64_any_dtype(b_x):
        return None
    a, b = a_x.dropna(), b_x.dropna()
    if a.empty or b.empty:
        return None
    low, high = max(a.min(), b.min()), min(a.max(), b.max())
    return (low, high) if low <= high else None
