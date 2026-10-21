from plot_studio.plotting.specs import build_plot_spec_from_builder


def test_build_plot_spec_omits_secondary_axis_when_disabled():
    spec = build_plot_spec_from_builder(
        title="Flow",
        x_col="time",
        y_cols=["q"],
        plot_type="Line",
        template="plotly_white",
        enable_secondary_axis=False,
        y2_cols=["temp"],
        yaxis_title_1="Flow",
        yaxis_title_2="Temp",
        color_col=None,
        agg=None,
        series_style={"q": {"color": "#123456", "width": 2, "dash": "solid"}},
    )

    assert spec["title"] == "Flow"
    assert spec["y2_cols"] == []
    assert spec["plot_type"] == "Line"
