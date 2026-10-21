from io import BytesIO

import pytest

from plot_studio.services.csv_reading import (
    CsvReadError,
    detect_separator_from_sample,
    read_csv_bytes,
    read_csv_input,
)


class UploadedBytes(BytesIO):
    def __init__(self, name: str, content: str):
        super().__init__(content.encode("utf-8"))
        self.name = name


def test_detect_separator_from_tab_sample():
    sample = "a\tb\tc\n1\t2\t3\n4\t5\t6\n"
    assert detect_separator_from_sample(sample) == "\t"


def test_read_csv_input_from_uploaded_file_trims_object_columns():
    uploaded = UploadedBytes("sample.csv", "name,value\n  alpha  ,1\nbeta,2\n")

    df, label, err, read_report = read_csv_input(
        uploaded,
        "",
        decimal=".",
        sep=",",
        header=0,
        skiprows=None,
    )

    assert err is None
    assert label == "sample.csv"
    assert df is not None
    assert read_report is not None
    assert df["name"].tolist() == ["alpha", "beta"]
    assert read_report.separator_label == "Comma (,)"
    assert read_report.header_label == "First row"


def test_read_csv_input_preserves_missing_object_values():
    uploaded = UploadedBytes("sample.csv", "name,value\n  alpha  ,1\n,2\n")

    df, _, err, _ = read_csv_input(
        uploaded,
        "",
        decimal=".",
        sep=",",
        header=0,
        skiprows=None,
    )

    assert err is None
    assert df is not None
    assert df["name"].iloc[0] == "alpha"
    assert df["name"].isna().iloc[1]


def test_read_csv_input_reports_auto_detected_separator():
    uploaded = UploadedBytes("sample.csv", "name;value\nalpha;1\nbeta;2\n")

    _, _, err, read_report = read_csv_input(
        uploaded,
        "",
        decimal=".",
        sep=None,
        header=0,
        skiprows=None,
    )

    assert err is None
    assert read_report is not None
    assert read_report.separator_auto_detected is True
    assert read_report.separator_label == "Auto-detected Semicolon (;)"


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


def test_read_csv_input_returns_a_message_for_missing_file(tmp_path):
    df, _, err, report = read_csv_input(
        None,
        str(tmp_path / "missing.csv"),
        decimal=".",
        sep=None,
        header=0,
        skiprows=None,
    )

    assert df is None
    assert report is None
    assert err is not None and "could not be opened" in err


def test_read_csv_input_reads_a_file_from_a_path(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("a;b\n1;2\n", encoding="utf-8")

    df, label, err, report = read_csv_input(
        None, str(path), decimal=".", sep=None, header=0, skiprows=None
    )

    assert err is None
    assert label == "data.csv"
    assert df is not None and df["b"].iloc[0] == 2
    assert report is not None and report.source_kind == "Server path"


def test_single_column_file_assumes_a_comma_and_says_so():
    df, report = _read(b"value\n1\n2\n")

    assert list(df.columns) == ["value"]
    assert report.separator_label == "Comma (,) (assumed)"
    assert any("comma was assumed" in warning for warning in report.warnings)
