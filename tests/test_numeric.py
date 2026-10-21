import pandas as pd

from plot_studio.services.numeric import coerce_numeric


def test_numeric_columns_are_returned_untouched():
    series = pd.Series([1.5, 2.5])

    converted, info = coerce_numeric(series)

    assert converted is series
    assert info.is_numeric and info.invalid_count == 0


def test_text_numbers_are_converted():
    converted, info = coerce_numeric(pd.Series(["1", " 2.5 ", "3"]))

    assert converted.tolist() == [1.0, 2.5, 3.0]
    assert info.is_numeric and info.invalid_count == 0


def test_a_few_bad_cells_are_ignored_and_described():
    values = ["1.5"] * 19 + ["--"]

    converted, info = coerce_numeric(pd.Series(values))

    assert info.is_numeric
    assert info.invalid_count == 1
    assert info.invalid_examples == ("--",)
    assert converted.isna().sum() == 1


def test_mostly_text_columns_stay_text():
    series = pd.Series(["a", "b", "c", "1"])

    converted, info = coerce_numeric(series)

    assert not info.is_numeric
    assert converted.tolist() == ["a", "b", "c", "1"]


def test_empty_cells_do_not_count_as_invalid():
    converted, info = coerce_numeric(pd.Series(["1", None, "", "3"]))

    assert info.is_numeric and info.invalid_count == 0
    assert converted.notna().sum() == 2


def test_decimal_commas_are_recognised_as_a_hint():
    _, info = coerce_numeric(pd.Series(["1,5", "2,5", "3,5"]))

    assert not info.is_numeric
    assert info.looks_like_decimal_comma


def test_all_empty_and_boolean_columns_are_not_numeric():
    assert not coerce_numeric(pd.Series([None, ""]))[1].is_numeric
    assert not coerce_numeric(pd.Series([True, False]))[1].is_numeric
