import pandas as pd

from plot_studio.services.date_parsing import (
    infer_dayfirst_from_series,
    parse_dates_flexible,
)


def test_infer_dayfirst_from_series_detects_european_dates():
    series = pd.Series(["31/01/2024", "01/02/2024", "15/03/2024"])
    assert infer_dayfirst_from_series(series) is True


def test_parse_dates_flexible_auto_detects_month_first_dates():
    df = pd.DataFrame({"date": ["01/31/2024", "02/15/2024"]})
    parsed = parse_dates_flexible(df, "date", date_mode="Auto-detect")
    assert parsed["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-31",
        "2024-02-15",
    ]


def test_parse_dates_flexible_prefers_explicit_format_override():
    df = pd.DataFrame({"date": ["03-31-2024", "04-01-2024"]})
    parsed = parse_dates_flexible(
        df,
        "date",
        date_mode="Day-first",
        date_format="%m-%d-%Y",
    )
    assert parsed["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-03-31",
        "2024-04-01",
    ]
