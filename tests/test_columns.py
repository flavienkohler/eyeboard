from plot_studio.services.columns import (
    guess_date_column,
    normalize_colname,
    resolve_column,
)


def test_normalize_colname_collapses_spacing_and_separators():
    assert normalize_colname(" Flow_Rate - Avg ") == "flow rate avg"


def test_resolve_column_matches_normalized_name():
    resolved = resolve_column("flow rate", ["Timestamp", "Flow_Rate", "Value"])
    assert resolved == "Flow_Rate"


def test_guess_date_column_prefers_date_keyword():
    guessed = guess_date_column(["station_id", "measurement_date", "value"])
    assert guessed == "measurement_date"
