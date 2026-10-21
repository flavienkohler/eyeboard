import pandas as pd

from plot_studio.services.dashboard_sync import (
    _compute_axis_range,
    coerce_component_sync_range,
    compute_dashboard_sync_x_range,
    prepare_dashboard_x_columns,
    sync_ranges_match,
)


def test_compute_dashboard_sync_x_range_for_datetime_series():
    df = pd.DataFrame(
        {
            "time_a": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "time_b": pd.to_datetime(["2024-01-01", "2024-01-04"]),
            "value": [1, 2],
        }
    )
    id_to_cfg = {
        "cfg-a": {"plots": [{"x_col": "time_a", "y_cols": ["value"], "y2_cols": []}]},
        "cfg-b": {"plots": [{"x_col": "time_b", "y_cols": ["value"], "y2_cols": []}]},
    }

    sync_range = compute_dashboard_sync_x_range(
        df,
        ["cfg-a", "cfg-b"],
        id_to_cfg,
        list(df.columns),
    )

    assert sync_range == (
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-04"),
    )


def test_compute_dashboard_sync_x_range_returns_none_for_mixed_x_types():
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "step": [1, 2],
            "value": [3, 4],
        }
    )
    id_to_cfg = {
        "cfg-a": {"plots": [{"x_col": "time", "y_cols": ["value"], "y2_cols": []}]},
        "cfg-b": {"plots": [{"x_col": "step", "y_cols": ["value"], "y2_cols": []}]},
    }

    sync_range = compute_dashboard_sync_x_range(
        df,
        ["cfg-a", "cfg-b"],
        id_to_cfg,
        list(df.columns),
    )

    assert sync_range is None


def test_prepare_dashboard_x_columns_parses_datetime_like_text_columns():
    df = pd.DataFrame(
        {
            "date": ["2024-01-02 00:00", "2024-01-03 00:00"],
            "value": [1, 2],
        }
    )
    id_to_cfg = {
        "cfg-a": {"plots": [{"x_col": "date", "y_cols": ["value"], "y2_cols": []}]},
    }

    prepared = prepare_dashboard_x_columns(
        df,
        ["cfg-a"],
        id_to_cfg,
        list(df.columns),
    )

    assert pd.api.types.is_datetime64_any_dtype(prepared["date"])


def test_coerce_component_sync_range_parses_datetime_payload():
    coerced = coerce_component_sync_range(
        ["2024-01-01 00:00:00", "2024-01-03 00:00:00"],
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-04")),
    )

    assert coerced == (
        pd.Timestamp("2024-01-01 00:00:00"),
        pd.Timestamp("2024-01-03 00:00:00"),
    )


def test_sync_ranges_match_handles_equal_timestamps():
    assert sync_ranges_match(
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")),
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")),
    )


def test_compute_axis_range_adds_padding_for_visible_values():
    df = pd.DataFrame({"a": [10.0, 20.0, 30.0]})

    computed = _compute_axis_range(df, ["a"])

    assert computed is not None
    assert computed[0] < 10.0
    assert computed[1] > 30.0
