import pandas as pd

from plot_studio.plotting.figures import (
    make_column_preview_figure,
    render_plot_from_spec,
    to_numeric_safe,
)


def test_render_plot_from_spec_returns_warning_for_missing_columns():
    df = pd.DataFrame({"time": [1, 2], "value": [10, 20]})
    spec = {"x_col": "time", "y_cols": ["missing"], "y2_cols": []}

    fig, warnings = render_plot_from_spec(df, spec, list(df.columns))

    assert fig is None
    assert warnings == [
        "Missing Y column: 'missing'",
        "No Y columns could be resolved.",
    ]


def test_render_plot_from_spec_reports_fuzzy_column_matches():
    df = pd.DataFrame({"Time Stamp": [1, 2], "Flow Rate": [10, 20]})
    spec = {"x_col": "time stamp", "y_cols": ["flow-rate"], "y2_cols": []}

    fig, warnings = render_plot_from_spec(df, spec, list(df.columns))

    assert fig is not None
    assert warnings == [
        "Matched X column 'time stamp' -> 'Time Stamp'",
        "Matched Y column 'flow-rate' -> 'Flow Rate'",
    ]


def test_make_column_preview_figure_for_numeric_series_returns_figure():
    series = pd.Series([1, 2, 3, 4])
    fig = make_column_preview_figure(series)

    assert fig is not None
    assert len(fig.data) == 1


def test_to_numeric_safe_converts_numeric_strings_and_keeps_text():
    df = pd.DataFrame(
        {
            "numbers": ["1", "2", "3"],
            "labels": ["a", "b", "c"],
        }
    )

    converted = to_numeric_safe(df, ["numbers", "labels"])

    assert converted["numbers"].tolist() == [1, 2, 3]
    assert converted["labels"].tolist() == ["a", "b", "c"]


def test_make_column_preview_figure_downsamples_numeric_series():
    series = pd.Series(range(1_000))

    fig = make_column_preview_figure(series, max_points=75)

    assert fig is not None
    assert len(fig.data[0].x) == 75
    assert fig.data[0].x[0] == 0
    assert fig.data[0].x[-1] == 999


def test_make_column_preview_figure_reuses_sorted_datetime_x_series():
    series = pd.Series([10, 20, 30, 40], index=[0, 1, 2, 3])
    x_series = pd.to_datetime(
        pd.Series(
            ["2024-01-04", "2024-01-01", "2024-01-03", "2024-01-02"],
            index=[0, 1, 2, 3],
        )
    ).sort_values(kind="stable")

    fig = make_column_preview_figure(
        series,
        x_series=x_series,
        x_label="date",
        x_sorted=True,
        max_points=3,
    )

    assert fig is not None
    assert list(fig.data[0].x) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-03"),
        pd.Timestamp("2024-01-04"),
    ]
    assert list(fig.data[0].y) == [20, 30, 10]
