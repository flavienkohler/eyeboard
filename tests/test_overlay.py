import plotly.graph_objects as go

from eyeboard.plotting.overlay import overlay_figures


def _figure(*traces):
    fig = go.Figure()
    for trace in traces:
        fig.add_trace(trace)
    return fig


def test_b_is_added_dashed_with_the_color_of_the_same_series_in_a():
    fig_a = _figure(
        go.Scatter(x=[1, 2], y=[1, 2], name="flow", mode="lines"),
        go.Scatter(x=[1, 2], y=[3, 4], name="temp", mode="lines"),
    )
    fig_b = _figure(
        go.Scatter(x=[1, 2], y=[2, 3], name="temp", mode="lines"),
        go.Scatter(x=[1, 2], y=[5, 6], name="flow", mode="lines"),
    )

    result = overlay_figures(fig_a, fig_b)

    by_name = {t.name: t for t in result.data}
    assert set(by_name) == {"flow (A)", "temp (A)", "flow (B)", "temp (B)"}
    assert by_name["flow (A)"].line.color == by_name["flow (B)"].line.color
    assert by_name["temp (A)"].line.color == by_name["temp (B)"].line.color
    assert by_name["flow (A)"].line.color != by_name["temp (A)"].line.color
    assert by_name["flow (B)"].line.dash == "dash"
    assert by_name["flow (A)"].line.dash is None
    assert by_name["flow (B)"].legendgroup == "flow"


def test_the_inputs_are_not_modified():
    fig_a = _figure(go.Scatter(x=[1], y=[1], name="flow", mode="lines"))
    fig_b = _figure(go.Scatter(x=[1], y=[2], name="flow", mode="lines"))

    overlay_figures(fig_a, fig_b)

    assert fig_a.data[0].name == "flow" and len(fig_a.data) == 1
    assert fig_b.data[0].name == "flow" and fig_b.data[0].line.dash is None


def test_markers_and_bars_are_told_apart_from_a():
    fig_a = _figure(
        go.Scatter(x=[1], y=[1], name="m", mode="markers"),
        go.Bar(x=[1], y=[1], name="b"),
    )
    fig_b = _figure(
        go.Scatter(x=[1], y=[2], name="m", mode="markers"),
        go.Bar(x=[1], y=[2], name="b"),
    )

    result = overlay_figures(fig_a, fig_b)

    by_name = {t.name: t for t in result.data}
    assert by_name["m (B)"].marker.symbol == "x"
    assert by_name["b (B)"].marker.opacity == 0.55
    assert by_name["b (A)"].marker.color == by_name["b (B)"].marker.color


def test_a_series_only_in_b_still_gets_a_color():
    fig_a = _figure(go.Scatter(x=[1], y=[1], name="flow", mode="lines"))
    fig_b = _figure(go.Scatter(x=[1], y=[2], name="extra", mode="lines"))

    result = overlay_figures(fig_a, fig_b)

    assert result.data[1].name == "extra (B)"
    assert result.data[1].line.color not in (None, result.data[0].line.color)
