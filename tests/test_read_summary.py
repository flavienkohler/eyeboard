from eyeboard.models import CsvReadReport, DateSettings, ReadOptions
from eyeboard.services.read_summary import detected_settings


def _report(**overrides):
    fields = {
        "source_kind": "Upload",
        "source_label": "a.csv",
        "row_count": 3,
        "column_count": 2,
        "separator_label": "Auto-detected Semicolon (;)",
        "separator_auto_detected": True,
        "decimal_label": "Comma (,)",
        "header_label": "First row",
        "encoding_label": "UTF-8",
    }
    fields.update(overrides)
    return CsvReadReport(**fields)


def test_detected_values_are_marked_auto_and_chosen_ones_are_not():
    settings = {
        s.name: s
        for s in detected_settings(
            _report(), ReadOptions(), DateSettings(column="t"), "day first"
        )
    }

    assert settings["Separator"].text() == "Semicolon (;) (auto)"
    assert settings["Decimal"].text() == "Comma (,)"
    assert settings["Encoding"].auto
    assert settings["Date column"].text() == "`t`"
    assert settings["Date order"].text() == "day first (auto)"


def test_forced_options_are_not_marked_auto():
    settings = {
        s.name: s
        for s in detected_settings(
            _report(separator_label="Semicolon (;)", separator_auto_detected=False),
            ReadOptions(sep=";", encoding="utf-8"),
            DateSettings(column="t", mode="Day-first"),
            "day first",
        )
    }

    assert not settings["Separator"].auto
    assert not settings["Encoding"].auto
    assert not settings["Date order"].auto


def test_no_date_column_is_said_plainly():
    settings = detected_settings(_report(), ReadOptions(), DateSettings(), None)

    assert settings[-1].text() == "none selected"
    assert "Date order" not in [s.name for s in settings]
