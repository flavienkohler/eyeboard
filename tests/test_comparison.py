import math

import pandas as pd
import pytest

from eyeboard.services.comparison import (
    compare_series,
    overlap,
    shift_to_start,
)


def _days(start, count):
    return pd.Series(pd.date_range(start, periods=count, freq="D"))


def test_identical_series_have_no_gap_and_full_correlation():
    x = _days("2020-01-01", 5)
    y = pd.Series([1.0, 3.0, 2.0, 5.0, 4.0])

    result = compare_series(x, y, x, y)

    assert result.points == 5
    assert result.rmse == 0 and result.mae == 0 and result.bias == 0
    assert result.correlation == pytest.approx(1.0)


def test_a_constant_offset_is_the_bias_and_the_error():
    x = _days("2020-01-01", 4)
    a = pd.Series([1.0, 2.0, 3.0, 4.0])

    result = compare_series(x, a, x, a + 2)

    assert result.bias == pytest.approx(2.0)
    assert result.rmse == pytest.approx(2.0)
    assert result.mae == pytest.approx(2.0)
    assert result.correlation == pytest.approx(1.0)


def test_bias_is_b_minus_a_and_signed():
    x = _days("2020-01-01", 3)
    a = pd.Series([5.0, 5.0, 5.0])

    assert compare_series(x, a, x, a - 1).bias == pytest.approx(-1.0)


def test_b_is_interpolated_onto_the_timestamps_of_a():
    a_x = _days("2020-01-01", 3)  # days 1, 2, 3
    b_x = pd.Series(pd.to_datetime(["2020-01-01", "2020-01-03"]))
    b = pd.Series([0.0, 10.0])  # a line: 0 on day 1, 5 on day 2, 10 on day 3
    a = pd.Series([0.0, 5.0, 10.0])

    result = compare_series(a_x, a, b_x, b)

    assert result.points == 3
    assert result.rmse == pytest.approx(0.0)


def test_only_the_shared_range_is_compared_and_nothing_is_extrapolated():
    a_x = _days("2020-01-01", 6)  # days 1..6
    b_x = _days("2020-01-04", 6)  # days 4..9
    y = pd.Series([1.0] * 6)

    result = compare_series(a_x, y, b_x, y)

    assert result.points == 3  # days 4, 5, 6 of A


def test_series_that_never_meet_cannot_be_compared():
    y = pd.Series([1.0, 2.0])

    assert compare_series(_days("2020-01-01", 2), y, _days("2021-01-01", 2), y) is None


def test_elapsed_alignment_lines_up_runs_started_at_different_times():
    a_x, b_x = _days("2020-01-01", 4), _days("2021-06-01", 4)
    a = pd.Series([1.0, 2.0, 3.0, 4.0])

    assert compare_series(a_x, a, b_x, a) is None  # different dates: no overlap
    result = compare_series(a_x, a, b_x, a, alignment="elapsed")

    assert result.points == 4 and result.rmse == 0


def test_missing_values_and_duplicate_x_are_handled():
    a_x = pd.Series(
        pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-02", "2020-01-03"])
    )
    a = pd.Series([1.0, 2.0, 4.0, None])  # duplicate day averaged, NaN dropped
    b = pd.Series([1.0, 3.0, 3.0, 9.0])

    result = compare_series(a_x, a, a_x, b)

    assert result.points == 2
    assert result.bias == pytest.approx(0.0)  # day 1: 0, day 2: 3 - mean(2, 4) = 0


def test_constant_series_have_no_correlation_but_still_a_gap():
    x = _days("2020-01-01", 3)
    flat = pd.Series([2.0, 2.0, 2.0])

    result = compare_series(x, flat, x, flat + 1)

    assert math.isnan(result.correlation)
    assert result.bias == pytest.approx(1.0)


def test_text_or_mixed_axes_cannot_be_compared():
    y = pd.Series([1.0, 2.0])

    assert compare_series(pd.Series(["a", "b"]), y, pd.Series(["a", "b"]), y) is None
    assert compare_series(_days("2020-01-01", 2), y, pd.Series([1, 2]), y) is None


def test_numeric_axes_are_aligned_like_dates():
    x = pd.Series([0.0, 1.0, 2.0])

    result = compare_series(
        x, pd.Series([0.0, 1.0, 2.0]), x, pd.Series([1.0, 2.0, 3.0])
    )

    assert result.bias == pytest.approx(1.0)


def test_shift_to_start_moves_b_to_where_a_begins():
    a_x, b_x = _days("2020-01-01", 3), _days("2021-06-10", 3)

    shifted = shift_to_start(b_x, a_x)

    assert shifted.min() == a_x.min()
    assert (shifted.diff().dropna() == pd.Timedelta(days=1)).all()
    assert b_x.min() == pd.Timestamp("2021-06-10")  # not modified


def test_overlap_returns_the_shared_range():
    low, high = overlap(_days("2020-01-01", 6), _days("2020-01-04", 6))

    assert low == pd.Timestamp("2020-01-04") and high == pd.Timestamp("2020-01-06")
    assert overlap(_days("2020-01-01", 2), _days("2021-01-01", 2)) is None
    assert overlap(pd.Series(["a"]), pd.Series(["a"])) is None


def _frame(start, offset=0.0):
    return pd.DataFrame(
        {
            "date": _days(start, 4),
            "flow": [1.0, 2.0, 3.0, 4.0],
            "temp": ["10", "11", "12", "13"],
        }
    ).assign(flow=lambda d: d["flow"] + offset)


def test_compare_plot_measures_every_series_with_matched_column_names():
    from helpers import make_plot

    from eyeboard.services.comparison import compare_plot

    spec = make_plot(x_col="date", y_cols=["Flow"], y2_cols=["temp"])

    result = compare_plot(spec, _frame("2020-01-01"), _frame("2020-01-01", offset=1))

    assert [name for name, _ in result.rows] == ["Flow", "temp"]
    assert result.rows[0][1].bias == pytest.approx(1.0)
    assert result.rows[1][1].bias == pytest.approx(0.0)  # text read as numbers
    assert result.notes == []


def test_compare_plot_says_what_could_not_be_compared():
    from helpers import make_plot

    from eyeboard.services.comparison import compare_plot

    a, b = _frame("2020-01-01"), _frame("2021-01-01")

    no_overlap = compare_plot(make_plot(x_col="date", y_cols=["flow"]), a, b)
    missing = compare_plot(
        make_plot(x_col="date", y_cols=["nope"]), a, _frame("2020-01-01")
    )
    grouped = compare_plot(
        make_plot(x_col="date", y_cols=["flow"], color_col="temp"), a, a
    )
    text_x = compare_plot(make_plot(x_col="temp", y_cols=["flow"]), a, a)

    assert no_overlap.rows == [] and "no shared range" in no_overlap.notes[0]
    assert "missing in A" in missing.notes[0]
    assert "grouped or aggregated" in grouped.notes[0]
    assert "dates or numbers" in text_x.notes[0]
