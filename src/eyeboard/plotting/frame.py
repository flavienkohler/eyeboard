"""Prepare the data frame behind one plot: pick columns, convert, aggregate."""

import pandas as pd

from eyeboard.dashboards.model import PlotSpec
from eyeboard.services.numeric import NumericConversion, coerce_numeric

_DECIMAL_COMMA_HINT = (
    " The values look like decimal commas: set Decimal to Comma in Reading options."
)


def _unique(values: list[str]) -> list[str]:
    """Drop duplicates while keeping the order."""
    return list(dict.fromkeys(values))


def _describe_conversion(column: str, info: NumericConversion) -> str | None:
    """Turn a conversion outcome into a message for the user, if one is needed."""
    hint = _DECIMAL_COMMA_HINT if info.looks_like_decimal_comma else ""
    if not info.is_numeric:
        return (
            f"Column '{column}' is not numeric; it is plotted as text categories."
            + hint
        )
    if info.invalid_count:
        examples = ", ".join(f"'{value}'" for value in info.invalid_examples)
        return (
            f"Column '{column}': {info.invalid_count:,} value(s) could not be read as "
            f"numbers and were ignored (e.g. {examples})." + hint
        )
    return None


def prepare_plot_frame(
    df: pd.DataFrame,
    spec: PlotSpec,
) -> tuple[pd.DataFrame, PlotSpec, list[str]]:
    """Build the frame a plot needs and return it with the adjusted spec.

    Only the columns used by the plot are copied. Series columns are read as
    numbers (problems are reported, never hidden), then aggregated by X when the
    spec asks for it. Returns ``(frame, spec, warnings)``; the returned spec
    lists only the series that are still plottable.
    """
    x_col = spec.x_col
    y_cols = list(spec.y_cols)
    y2_cols = list(spec.y2_cols)
    color_col = spec.color_col
    agg = spec.agg
    series_cols = _unique(y_cols + y2_cols)
    warnings: list[str] = []

    needed = _unique([c for c in [x_col, *series_cols, color_col] if c])
    plot_df = df[needed].copy()

    conversions: dict[str, NumericConversion] = {}
    for column in series_cols:
        plot_df[column], conversions[column] = coerce_numeric(plot_df[column])
        message = _describe_conversion(column, conversions[column])
        if message:
            warnings.append(message)

    adjusted = spec
    if not agg:
        return plot_df, adjusted, warnings

    numeric_cols = [c for c in series_cols if conversions[c].is_numeric]
    for column in series_cols:
        if column not in numeric_cols:
            warnings.append(
                f"Column '{column}' is not numeric and cannot be aggregated; it was left out."
            )
    adjusted = spec.model_copy(
        update={
            "y_cols": [c for c in y_cols if c in numeric_cols],
            "y2_cols": [c for c in y2_cols if c in numeric_cols],
        }
    )
    if not numeric_cols:
        warnings.append("No numeric Y column is left to aggregate.")
        return plot_df, adjusted, warnings

    keys = _unique([c for c in [x_col, color_col] if c])
    grouped = plot_df.groupby(keys, dropna=False)[numeric_cols]
    return getattr(grouped, agg)().reset_index(), adjusted, warnings
