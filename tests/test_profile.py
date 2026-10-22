import pandas as pd

from eyeboard.services.profile import profile_columns, profiles_to_frame


def _by_name(df):
    return {p.name: p for p in profile_columns(df)}


def test_numbers_dates_and_text_are_told_apart():
    df = pd.DataFrame(
        {
            "t": pd.to_datetime(["2020-01-01", "2020-01-03"]),
            "q": [1.5, 2.5],
            "s": ["a", "b"],
        }
    )

    profiles = _by_name(df)

    assert [profiles[n].kind for n in ("t", "q", "s")] == ["date", "number", "text"]
    assert profiles["q"].minimum == "1.5" and profiles["q"].maximum == "2.5"
    assert profiles["t"].minimum.startswith("2020-01-01")
    assert profiles["s"].minimum == ""


def test_distinct_is_counted_for_numbers_too_and_exactly():
    df = pd.DataFrame({"q": [0.1, 0.1 + 1e-12, 0.1]})

    assert _by_name(df)["q"].distinct == 2


def test_missing_values_constant_and_empty_columns_are_flagged():
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [5, 5, 5], "c": [None, None, None]})

    profiles = _by_name(df)

    assert profiles["a"].missing_count == 1
    assert profiles["a"].missing_share == 1 / 3
    assert profiles["b"].checks == ("constant",)
    assert profiles["c"].checks == ("empty",)


def test_numbers_with_a_decimal_comma_are_flagged():
    df = pd.DataFrame({"q": ["1,5", "2,5", "3,25"]})

    profile = _by_name(df)["q"]

    assert profile.kind == "text"
    assert profile.decimal_comma
    assert any("Decimal" in check for check in profile.checks)


def test_text_that_is_mostly_numbers_reports_what_could_not_be_read():
    df = pd.DataFrame({"q": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "n/a"]})

    profile = _by_name(df)["q"]

    assert profile.kind == "number"
    assert profile.maximum == "9"
    assert "1 value(s) are not numbers ('n/a')" in profile.checks[0]


def test_the_display_table_has_one_row_per_column():
    frame = profiles_to_frame(profile_columns(pd.DataFrame({"a": [1], "b": ["x"]})))

    assert list(frame["column"]) == ["a", "b"]
    assert list(frame.columns)[:3] == ["column", "type", "missing %"]


def test_a_row_counter_a_constant_and_an_empty_column_are_recognised():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "const": [7, 7, 7, 7],
            "none": [None, None, None, None],
            "flow": [1.5, 0.5, 2.5, 1.0],
        }
    )

    profiles = _by_name(df)

    assert profiles["id"].index_like and not profiles["flow"].index_like
    assert profiles["const"].constant and not profiles["const"].empty
    assert profiles["none"].empty and not profiles["none"].constant


def test_a_first_plot_shows_the_first_real_measurement():
    from eyeboard.services.profile import suggested_series

    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "const": [7, 7, 7, 7],
            "label": ["a", "b", "c", "d"],
            "flow": [1.5, 0.5, 2.5, 1.0],
            "temp": [3.0, 4.0, 5.0, 6.5],
        }
    )

    assert suggested_series(profile_columns(df)) == ["flow"]


def test_the_first_plot_falls_back_to_a_number_when_nothing_better_exists():
    from eyeboard.services.profile import suggested_series

    only_counters = pd.DataFrame({"id": [1, 2, 3], "text": ["a", "b", "c"]})
    no_numbers = pd.DataFrame({"text": ["a", "b"]})

    assert suggested_series(profile_columns(only_counters)) == ["id"]
    assert suggested_series(profile_columns(no_numbers)) == []
