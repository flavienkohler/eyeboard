import os

import pandas as pd
import pytest
import streamlit as st

from eyeboard.models import DateSettings, ReadOptions
from eyeboard.services.csv_reading import CsvReadError
from eyeboard.services.dataset import (
    DataSource,
    load_table,
    parse_table,
    source_from_path,
    source_from_upload,
    summarize_date_parsing,
)
from eyeboard.ui.cache import load_table_cached, parse_table_cached

CSV = b"date;value\n01/03/2020;1,5\n02/03/2020;2,5\n"
OPTIONS = ReadOptions(decimal=",")


class FakeUpload:
    name = "up.csv"
    file_id = "abc123"

    def getvalue(self):
        return CSV


def _source(calls: list[int] | None = None, key: str = "k1") -> DataSource:
    def read_bytes():
        if calls is not None:
            calls.append(1)
        return CSV

    return DataSource(key=key, label="x.csv", kind="Upload", read_bytes=read_bytes)


@pytest.fixture(autouse=True)
def _clear_caches():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def test_load_table_reads_the_source_with_the_options():
    df, report = load_table(_source(), OPTIONS)

    assert list(df.columns) == ["date", "value"]
    assert df["value"].tolist() == [1.5, 2.5]
    assert report.source_label == "x.csv" and report.source_kind == "Upload"


def test_load_table_accepts_tuple_headers():
    raw = b"group,group\nname,unit\n1,2\n"
    source = DataSource("k", "m.csv", "Upload", lambda: raw)

    df, _ = load_table(source, ReadOptions(header=(0, 1)))

    assert list(df.columns) == ["group | name", "group | unit"]


def test_source_from_upload_uses_the_upload_id_as_key():
    source = source_from_upload(FakeUpload())

    assert source.key == "upload:abc123"
    assert source.label == "up.csv" and source.read_bytes() == CSV


def test_source_key_of_a_path_changes_when_the_file_changes(tmp_path):
    path = tmp_path / "data.csv"
    path.write_bytes(CSV)
    first = source_from_path(path)

    path.write_bytes(CSV + b"03/03/2020;3,5\n")
    os.utime(path, ns=(10**18, 10**18))  # make the change visible to the key
    second = source_from_path(path)

    assert first.key != second.key
    assert second.label == "data.csv" and second.kind == "Server path"


def test_parse_table_parses_dates_and_summarises():
    df, _ = load_table(_source(), OPTIONS)

    parsed = parse_table(df, DateSettings(column="date", mode="Day-first"))

    assert pd.api.types.is_datetime64_any_dtype(parsed.df["date"])
    assert parsed.df["date"].iloc[0] == pd.Timestamp("2020-03-01")
    assert parsed.date_parse_success_count == 2
    assert parsed.date_parse_candidate_count == 2
    assert parsed.date_parse_warning is None


def test_parse_table_without_a_date_column_returns_the_table_unchanged():
    df, _ = load_table(_source(), OPTIONS)

    parsed = parse_table(df, DateSettings())

    assert parsed.df.equals(df) and parsed.date_parse_candidate_count == 0


def test_a_low_parse_rate_produces_a_warning():
    df = pd.DataFrame({"d": ["2020-01-01", "x", "y", "z"]})
    parsed = pd.DataFrame({"d": pd.to_datetime(["2020-01-01", None, None, None])})

    success, candidates, warning = summarize_date_parsing(df, parsed, "d")

    assert (success, candidates) == (1, 4)
    assert warning is not None and "1 of 4" in warning


def test_the_cache_reads_a_source_only_once():
    calls: list[int] = []
    source = _source(calls)

    first = load_table_cached(source, OPTIONS)
    second = load_table_cached(source, OPTIONS)

    assert len(calls) == 1
    assert first[2] is None and first[0].equals(second[0])


def test_the_cache_is_keyed_by_source_and_options():
    calls: list[int] = []

    load_table_cached(_source(calls, "a"), OPTIONS)
    load_table_cached(_source(calls, "b"), OPTIONS)
    load_table_cached(_source(calls, "a"), ReadOptions(decimal=".", sep=";"))
    load_table_cached(_source(calls, "a"), OPTIONS)

    assert len(calls) == 3


def test_cached_tables_cannot_be_changed_through_a_previous_result():
    source = _source()
    first, _, _ = load_table_cached(source, OPTIONS)
    first.loc[0, "value"] = 999.0

    again, _, _ = load_table_cached(source, OPTIONS)

    assert again.loc[0, "value"] == 1.5


def test_load_errors_come_back_as_messages_and_are_not_cached():
    calls: list[int] = []

    def read_bytes():
        calls.append(1)
        return b""

    source = DataSource("empty", "e.csv", "Upload", read_bytes)
    with pytest.raises(CsvReadError):
        load_table(source, OPTIONS)

    for _ in range(2):
        df, report, error = load_table_cached(source, OPTIONS)
        assert df is None and report is None and "empty" in error
    assert len(calls) == 3  # errors are not cached: the user may fix the file


def test_parse_table_cached_matches_the_pure_function():
    df, _ = load_table(_source(), OPTIONS)
    settings = DateSettings(column="date", mode="Day-first")

    cached = parse_table_cached(_source(), OPTIONS, settings, df)

    assert cached.df.equals(parse_table(df, settings).df)
