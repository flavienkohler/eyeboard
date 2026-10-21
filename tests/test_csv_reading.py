import pytest

from eyeboard.services.csv_reading import (
    CsvReadError,
    detect_separator_from_sample,
    read_csv_bytes,
)


def test_detect_separator_from_tab_sample():
    sample = "a\tb\tc\n1\t2\t3\n4\t5\t6\n"
    assert detect_separator_from_sample(sample) == "\t"


def _read(raw: bytes, **overrides):
    options = {"decimal": ".", "sep": None, "header": 0, "skiprows": None}
    options.update(overrides)
    return read_csv_bytes(raw, **options)


def test_windows_1252_file_is_decoded_with_a_warning():
    raw = "date;débit;temp\n01/03/2020;1,5;2,1\n".encode("cp1252")

    df, report = _read(raw, decimal=",")

    assert list(df.columns) == ["date", "débit", "temp"]
    assert df["débit"].iloc[0] == 1.5
    assert report.encoding_label == "Windows-1252"
    assert any("not valid UTF-8" in warning for warning in report.warnings)


def test_utf8_bom_is_not_kept_in_the_first_column_name():
    raw = b"\xef\xbb\xbfdate,value\n2020-01-01,1\n"

    df, report = _read(raw, decimal=",")

    assert list(df.columns) == ["date", "value"]
    assert report.encoding_label == "UTF-8"


def test_utf16_file_is_read_through_its_byte_order_mark():
    raw = "date,value\n2020-01-01,1\n".encode("utf-16")

    df, report = _read(raw)

    assert list(df.columns) == ["date", "value"]
    assert report.encoding_label == "UTF-16"


def test_explicit_encoding_overrides_detection_and_reports_failures():
    raw = "name;v\nécole;1\n".encode("cp1252")

    df, report = _read(raw, encoding="cp1252")
    assert df["name"].iloc[0] == "école"
    assert report.encoding_label == "Windows-1252"

    with pytest.raises(CsvReadError, match="decoded"):
        _read(raw, encoding="utf-8")


def test_empty_columns_are_dropped_and_reported():
    raw = b"date,a,,b\n2020-01-01,1,,3\n2020-01-02,2,,4\n"

    df, report = _read(raw)

    assert list(df.columns) == ["date", "a", "b"]
    assert any("Dropped 1 empty column" in warning for warning in report.warnings)


def test_renamed_duplicate_columns_are_reported():
    raw = b"date,a,a\n2020-01-01,1,2\n"

    df, report = _read(raw)

    assert list(df.columns) == ["date", "a", "a.1"]
    assert any("a.1" in warning for warning in report.warnings)


def test_empty_input_gives_a_user_message():
    with pytest.raises(CsvReadError, match="empty"):
        _read(b"")


def test_single_column_file_assumes_a_comma_and_says_so():
    df, report = _read(b"value\n1\n2\n")

    assert list(df.columns) == ["value"]
    assert report.separator_label == "Comma (,) (assumed)"
    assert any("comma was assumed" in warning for warning in report.warnings)


def test_object_columns_are_trimmed_and_missing_values_are_kept():
    df, _ = _read(b"name,value\n  alpha  ,1\n,2\n")

    assert df["name"].iloc[0] == "alpha"
    assert df["name"].isna().iloc[1]


def test_report_describes_separator_header_and_decimal():
    _, report = _read(b"name;value\nalpha;1\nbeta;2\n", sep=";")

    assert report.separator_label == "Semicolon (;)"
    assert report.header_label == "First row"
    assert report.decimal_label == "Dot (.)"
    assert report.row_count == 2 and report.column_count == 2


def test_auto_detected_separator_is_reported_as_such():
    _, report = _read(b"name;value\nalpha;1\nbeta;2\n")

    assert report.separator_auto_detected is True
    assert report.separator_label == "Auto-detected Semicolon (;)"
