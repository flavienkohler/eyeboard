import json

import pytest
from pydantic import ValidationError

from eyeboard.dashboards.document import (
    SCHEMA_VERSION,
    load_document_text,
    migrate_v1_to_v2,
    parse_document,
    serialize_document,
)
from eyeboard.dashboards.model import Dashboard, PlotSpec, SeriesStyle


def _plot(**overrides):
    plot = {"x_col": "date", "y_cols": ["flow"]}
    plot.update(overrides)
    return plot


def _dashboard(**overrides):
    dashboard = {"name": "Board", "plots": [_plot()]}
    dashboard.update(overrides)
    return dashboard


def _v1_plot(**overrides):
    plot = {
        "id": "p1",
        "title": "q",
        "x_col": "date",
        "y_cols": ["flow"],
        "y2_cols": [],
        "plot_type": "Line",
        "template": "plotly_white",
        "yaxis_title_1": None,
        "yaxis_title_2": None,
        "color_col": None,
        "agg": None,
        "series_style": {"flow": {"color": "#636EFA", "width": 2, "dash": "solid"}},
    }
    plot.update(overrides)
    return plot


# --- models -----------------------------------------------------------------


def test_plot_spec_fills_defaults_and_generates_an_id():
    plot = PlotSpec(x_col="date", y_cols=["flow"])

    assert plot.plot_type == "Line"
    assert plot.theme == "plotly_white"
    assert plot.y2_cols == [] and plot.series_style == {}
    assert plot.id


def test_plot_spec_requires_at_least_one_series():
    with pytest.raises(ValidationError, match="at least one Y series"):
        PlotSpec(x_col="date")


def test_plot_spec_accepts_a_series_on_the_secondary_axis_only():
    assert PlotSpec(x_col="date", y2_cols=["rain"]).y2_cols == ["rain"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"plot_type": "Pie"},
        {"agg": "mode"},
        {"theme": "neon"},
        {"y_cols": [""]},
        {"x_col": "  "},
        {"unknown_key": 1},
        {"series_style": {"flow": {"dash": "wavy"}}},
        {"series_style": {"flow": {"width": -1}}},
    ],
)
def test_plot_spec_rejects_invalid_values(overrides):
    with pytest.raises(ValidationError):
        PlotSpec(**{"x_col": "date", "y_cols": ["flow"], **overrides})


def test_blank_optional_strings_become_none():
    plot = PlotSpec(
        x_col="date", y_cols=["flow"], title=" ", color_col="", agg="", yaxis_title_1=""
    )

    assert plot.title is None and plot.color_col is None and plot.agg is None
    assert plot.yaxis_title_1 is None


def test_null_axis_lists_are_read_as_empty():
    plot = PlotSpec.model_validate(
        {"x_col": "date", "y_cols": ["flow"], "y2_cols": None}
    )

    assert plot.y2_cols == []


def test_series_style_is_parsed_into_models():
    plot = PlotSpec(
        x_col="date",
        y_cols=["flow"],
        series_style={"flow": {"color": "#fff", "width": 3}},
    )

    assert isinstance(plot.series_style["flow"], SeriesStyle)
    assert plot.series_style["flow"].width == 3


def test_dashboard_needs_a_name_and_a_plot():
    with pytest.raises(ValidationError):
        Dashboard.model_validate({"name": " ", "plots": [_plot()]})
    with pytest.raises(ValidationError):
        Dashboard.model_validate({"name": "Board", "plots": []})


def test_dashboard_gets_an_id_and_a_creation_time():
    dashboard = Dashboard.model_validate(_dashboard())

    assert dashboard.id and dashboard.created_at.endswith("Z")


# --- migration and parsing --------------------------------------------------


def test_migrate_v1_renames_template_to_theme_without_touching_the_input():
    original = [{"name": "d", "plots": [_v1_plot(template="plotly_dark")]}]

    migrated = migrate_v1_to_v2(original)

    assert migrated[0]["plots"][0]["theme"] == "plotly_dark"
    assert "template" not in migrated[0]["plots"][0]
    assert original[0]["plots"][0]["template"] == "plotly_dark"


def test_a_v1_list_is_loaded_and_flagged_as_migrated():
    raw = [
        {
            "id": "d1",
            "name": "debit",
            "created_at": "2026-02-24T09:29:16.132046Z",
            "plots": [_v1_plot()],
        }
    ]

    result = parse_document(raw)

    assert result.source_version == 1 and result.migrated
    assert result.problems == [] and not result.blocked
    plot = result.dashboards[0].plots[0]
    assert plot.theme == "plotly_white"
    assert plot.series_style["flow"].color == "#636EFA"


def test_invalid_entries_are_reported_and_kept_aside_not_dropped():
    good = {"id": "d1", "name": "ok", "plots": [_v1_plot()]}
    bad = {"id": "d2", "name": "broken", "plots": [_v1_plot(plot_type="Pie")]}

    result = parse_document([good, bad])

    assert [d.name for d in result.dashboards] == ["ok"]
    assert result.skipped == [bad]
    assert any("'broken'" in p and "plots.0.plot_type" in p for p in result.problems)


def test_non_object_entries_are_reported():
    result = parse_document(["nope"])

    assert result.dashboards == [] and result.skipped == ["nope"]
    assert result.problems


def test_duplicate_dashboard_ids_are_reported():
    entry = {"id": "same", "name": "a", "plots": [_v1_plot()]}

    result = parse_document([entry, {**entry, "name": "b"}])

    assert len(result.dashboards) == 1
    assert any("duplicate dashboard id" in p for p in result.problems)


def test_a_newer_schema_version_blocks_saving():
    result = parse_document({"schema_version": SCHEMA_VERSION + 1, "dashboards": []})

    assert result.blocked
    assert "Update EyeBoard" in result.problems[0]


@pytest.mark.parametrize(
    "raw",
    [42, "text", {"dashboards": []}, {"schema_version": True, "dashboards": []}],
)
def test_unrecognised_documents_are_blocked(raw):
    assert parse_document(raw).blocked


def test_invalid_json_text_is_blocked_with_a_message():
    result = load_document_text("{not json")

    assert result.blocked and "not valid JSON" in result.problems[0]


def test_serialised_document_round_trips():
    dashboard = Dashboard.model_validate(
        _dashboard(plots=[_plot(series_style={"flow": {"color": "#123456"}})])
    )

    text = serialize_document([dashboard])
    result = load_document_text(text)

    assert json.loads(text)["schema_version"] == SCHEMA_VERSION
    assert not result.migrated and result.problems == []
    assert result.dashboards == [dashboard]
