import pandas as pd
from helpers import make_plot

from eyeboard.plotting.frame import prepare_plot_frame


def _spec(**overrides):
    return make_plot(**{"x_col": "t", "y_cols": ["v"], **overrides})


def test_only_the_columns_of_the_plot_are_kept():
    df = pd.DataFrame({"t": [1, 2], "v": [1.0, 2.0], "other": ["a", "b"]})

    plot_df, _, warnings = prepare_plot_frame(df, _spec())

    assert list(plot_df.columns) == ["t", "v"]
    assert warnings == []


def test_bad_cells_are_reported_not_hidden():
    df = pd.DataFrame({"t": range(20), "v": ["1.5"] * 19 + ["--"]})

    plot_df, _, warnings = prepare_plot_frame(df, _spec())

    assert pd.api.types.is_numeric_dtype(plot_df["v"])
    assert len(warnings) == 1
    assert "'--'" in warnings[0] and "ignored" in warnings[0]


def test_text_series_are_flagged_but_still_plotted():
    df = pd.DataFrame({"t": [1, 2, 3], "v": ["a", "b", "c"]})

    plot_df, spec, warnings = prepare_plot_frame(df, _spec())

    assert spec.y_cols == ["v"]
    assert plot_df["v"].tolist() == ["a", "b", "c"]
    assert "not numeric" in warnings[0]


def test_decimal_comma_hint_is_added_to_the_message():
    df = pd.DataFrame({"t": [1, 2], "v": ["1,5", "2,5"]})

    _, _, warnings = prepare_plot_frame(df, _spec())

    assert "Decimal" in warnings[0]


def test_aggregation_groups_by_x_on_numeric_series():
    df = pd.DataFrame({"t": [1, 1, 2], "v": [1.0, 3.0, 5.0]})

    plot_df, _, warnings = prepare_plot_frame(df, _spec(agg="mean"))

    assert plot_df["t"].tolist() == [1, 2]
    assert plot_df["v"].tolist() == [2.0, 5.0]
    assert warnings == []


def test_aggregation_keeps_the_color_column():
    df = pd.DataFrame({"t": [1, 1, 1], "v": [1.0, 3.0, 5.0], "g": ["a", "a", "b"]})

    plot_df, _, _ = prepare_plot_frame(df, _spec(agg="sum", color_col="g"))

    assert sorted(zip(plot_df["g"], plot_df["v"], strict=True)) == [
        ("a", 4.0),
        ("b", 5.0),
    ]


def test_aggregation_leaves_out_text_series_and_says_so():
    df = pd.DataFrame({"t": [1, 1], "v": [1.0, 3.0], "s": ["a", "b"]})

    _, spec, warnings = prepare_plot_frame(df, _spec(y_cols=["v", "s"], agg="max"))

    assert spec.y_cols == ["v"]
    assert any("cannot be aggregated" in warning for warning in warnings)


def test_aggregation_with_no_numeric_series_leaves_nothing_to_plot():
    df = pd.DataFrame({"t": [1, 1], "s": ["a", "b"]})

    _, spec, warnings = prepare_plot_frame(df, _spec(y_cols=["s"], agg="sum"))

    assert spec.y_cols == [] and spec.y2_cols == []
    assert "No numeric Y column" in warnings[-1]
