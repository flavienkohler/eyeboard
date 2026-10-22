import numpy as np
import pandas as pd
import pytest
from helpers import make_dashboard, make_plot

from eyeboard.plotting.builder import WEBGL_MIN_POINTS, make_figure

PLOT_TYPES = ["Line", "Scatter", "Bar", "Area"]


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "t": range(6),
            "a": [1.0, 2.0, 3.0, 2.0, 1.0, 2.0],
            "b": [2.0, 1.0, 2.0, 3.0, 2.0, 1.0],
            "c": [10.0, 20.0, 30.0, 20.0, 10.0, 20.0],
            "g": ["x", "x", "y", "y", "x", None],
        }
    )


def spec(**overrides):
    return make_plot(**{"x_col": "t", "y_cols": ["a", "b"], **overrides})


# --- one code path for every combination ------------------------------------


@pytest.mark.parametrize("plot_type", PLOT_TYPES)
def test_one_trace_per_series_and_the_data_is_unchanged(df, plot_type):
    fig = make_figure(df, spec(plot_type=plot_type))

    assert [t.name for t in fig.data] == ["a", "b"]
    assert all(t.yaxis == "y" for t in fig.data)
    assert list(fig.data[0].x) == list(df["t"])
    assert list(fig.data[1].y) == list(df["b"])


@pytest.mark.parametrize("plot_type", PLOT_TYPES)
def test_the_secondary_axis_adds_traces_without_changing_the_primary_ones(
    df, plot_type
):
    single = make_figure(df, spec(plot_type=plot_type))
    double = make_figure(df, spec(plot_type=plot_type, y2_cols=["c"]))

    assert [t.name for t in double.data] == ["a", "b", "c (Y2)"]
    assert [t.yaxis for t in double.data] == ["y", "y", "y2"]
    # The same type of trace is used on both axes, and on both code paths.
    assert [t.type for t in double.data[:2]] == [t.type for t in single.data]
    assert double.data[2].type == single.data[0].type
    assert double.layout.yaxis2.overlaying == "y"
    assert double.layout.yaxis2.side == "right"
    assert "yaxis2" not in single.layout


def test_plot_types_map_to_the_expected_traces(df):
    assert make_figure(df, spec(plot_type="Line")).data[0].mode == "lines"
    assert make_figure(df, spec(plot_type="Scatter")).data[0].mode == "markers"
    assert make_figure(df, spec(plot_type="Bar")).data[0].type == "bar"
    area = make_figure(df, spec(plot_type="Area")).data[0]
    assert area.fill == "tozeroy" and area.stackgroup is None  # overlapping


def test_bars_are_grouped_not_stacked(df):
    assert make_figure(df, spec(plot_type="Bar")).layout.barmode == "group"
    with_y2 = make_figure(df, spec(plot_type="Bar", y2_cols=["c"]))
    assert with_y2.layout.barmode == "group"


# --- WebGL for big traces ----------------------------------------------------


def _big_frame(n):
    return pd.DataFrame({"t": np.arange(n), "a": np.arange(n, dtype=float)})


@pytest.mark.parametrize(
    ("plot_type", "expected"),
    [
        ("Line", "scattergl"),
        ("Scatter", "scattergl"),
        ("Area", "scatter"),
        ("Bar", "bar"),
    ],
)
def test_big_traces_use_webgl_except_areas_and_bars(plot_type, expected):
    frame = _big_frame(WEBGL_MIN_POINTS + 1)

    fig = make_figure(frame, spec(plot_type=plot_type, y_cols=["a"]))

    assert fig.data[0].type == expected


@pytest.mark.parametrize("plot_type", ["Line", "Scatter"])
def test_small_traces_stay_in_svg(plot_type):
    frame = _big_frame(WEBGL_MIN_POINTS)

    fig = make_figure(frame, spec(plot_type=plot_type, y_cols=["a"]))

    assert fig.data[0].type == "scatter"


# --- styles ------------------------------------------------------------------

STYLE = {"a": {"color": "#ff0000", "width": 4, "dash": "dot"}}


@pytest.mark.parametrize("y2_cols", [[], ["c"]])
@pytest.mark.parametrize("plot_type", ["Line", "Area"])
def test_line_styles_apply_with_and_without_a_secondary_axis(df, plot_type, y2_cols):
    fig = make_figure(
        df, spec(plot_type=plot_type, y2_cols=y2_cols, series_style=STYLE)
    )

    line = fig.data[0].line
    assert (line.color, line.width, line.dash) == ("#ff0000", 4, "dot")
    assert fig.data[1].line.color is None  # unstyled series keep the palette


@pytest.mark.parametrize("y2_cols", [[], ["c"]])
@pytest.mark.parametrize("plot_type", ["Scatter", "Bar"])
def test_marker_color_applies_with_and_without_a_secondary_axis(df, plot_type, y2_cols):
    fig = make_figure(
        df, spec(plot_type=plot_type, y2_cols=y2_cols, series_style=STYLE)
    )

    assert fig.data[0].marker.color == "#ff0000"


def test_a_style_can_target_a_secondary_axis_series(df):
    style = {"c": {"color": "#00ff00", "width": 3}}

    fig = make_figure(df, spec(y2_cols=["c"], series_style=style))

    assert fig.data[2].line.color == "#00ff00" and fig.data[2].line.width == 3


# --- color by group ----------------------------------------------------------


@pytest.mark.parametrize("y2_cols", [[], ["c"]])
def test_color_by_makes_one_trace_per_series_and_group(df, y2_cols):
    fig = make_figure(df, spec(color_col="g", y2_cols=y2_cols))

    names = [t.name for t in fig.data]
    groups = 3  # x, y and the empty one
    assert len(names) == (2 + len(y2_cols)) * groups
    assert {"a · x", "a · y", "a · (empty)", "b · x"} <= set(names)
    if y2_cols:
        assert "c · x (Y2)" in names


def test_groups_keep_their_own_rows_and_series_stay_apart(df):
    fig = make_figure(df, spec(color_col="g", plot_type="Scatter"))

    a_x = next(t for t in fig.data if t.name == "a · x")
    b_x = next(t for t in fig.data if t.name == "b · x")
    assert list(a_x.x) == [0, 1, 4] and list(a_x.y) == [1.0, 2.0, 1.0]
    assert list(b_x.y) == [2.0, 1.0, 2.0]  # not merged with series a


def test_with_color_by_the_series_color_is_ignored_but_width_and_dash_stay(df):
    fig = make_figure(df, spec(color_col="g", series_style=STYLE))

    traces = [t for t in fig.data if t.name.startswith("a ·")]
    assert all(t.line.color is None for t in traces)
    assert all(t.line.width == 4 and t.line.dash == "dot" for t in traces)


# --- layout ------------------------------------------------------------------


def test_theme_title_margin_and_legend_are_set_once_for_every_figure(df):
    plain = make_figure(df, spec(theme="plotly_dark"))
    titled = make_figure(df, spec(title="Flow", y2_cols=["c"]))

    assert plain.layout.template.layout.paper_bgcolor == "rgb(17,17,17)"
    assert plain.layout.margin.t == 20 and titled.layout.margin.t == 85
    assert titled.layout.title.text == "Flow"
    assert plain.layout.title.text is None
    for fig in (plain, titled):
        assert fig.layout.legend.orientation == "h"


def test_theme_none_keeps_the_plotly_default(df):
    fig = make_figure(df, spec(theme="none"))

    assert fig.layout.template.layout.colorway is not None


def test_axis_titles_use_custom_text_then_the_single_series_name(df):
    single = make_figure(df, spec(y_cols=["a"]))
    several = make_figure(df, spec())
    custom = make_figure(
        df,
        spec(yaxis_title_1="Flow (m3/s)", y2_cols=["c"], yaxis_title_2="Rain"),
    )

    assert single.layout.xaxis.title.text == "t"
    assert single.layout.yaxis.title.text == "a"
    assert several.layout.yaxis.title.text is None
    assert custom.layout.yaxis.title.text == "Flow (m3/s)"
    assert custom.layout.yaxis2.title.text == "Rain"


def test_an_empty_table_gives_an_empty_figure(df):
    fig = make_figure(df.iloc[0:0], spec(color_col="g"))

    assert len(fig.data) == 0


# --- dashboards --------------------------------------------------------------


def test_dashboard_figures_map_secondary_traces_to_the_secondary_axis(df):
    from eyeboard.ui.tabs.dashboard import build_dashboard_figure

    dashboard = make_dashboard(
        plots=[
            make_plot(x_col="t", y_cols=["a"], y2_cols=["c"], title="one"),
            make_plot(x_col="t", y_cols=["b"], title="two"),
        ]
    )

    fig, warnings = build_dashboard_figure(
        dashboard, df, list(df.columns), sync_x_axis=True, sync_x_range=None
    )

    assert fig is not None and [w for _, w in warnings] == [[], []]
    assert [t.name for t in fig.data] == ["a", "c (Y2)", "b"]
    # Plot one has two Y axes, plot two has one: three Y axes in total.
    layout = fig.layout.to_plotly_json()
    assert len([key for key in layout if key.startswith("yaxis")]) == 3
