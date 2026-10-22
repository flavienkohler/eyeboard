import pandas as pd
import plotly.graph_objects as go

from eyeboard.plotting.export import csv_bytes, file_stem, html_bytes, png_config


def test_the_html_chart_is_standalone_and_holds_the_data():
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], name="flow"))

    page = html_bytes(fig).decode("utf-8")

    assert page.startswith("<html>") and "flow" in page
    external_script = '<script src="https://'
    assert external_script not in page  # the library is inside the file


def test_the_csv_starts_with_a_bom_and_keeps_accents():
    raw = csv_bytes(pd.DataFrame({"débit": [1.5], "t": ["a"]}))

    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").splitlines() == ["débit,t", "1.5,a"]


def test_file_names_are_safe():
    assert file_stem(" Flow board / run #2 ") == "Flow_board_run_2"
    assert file_stem("///") == "eyeboard"
    assert png_config("My plot")["toImageButtonOptions"]["filename"] == "My_plot"
