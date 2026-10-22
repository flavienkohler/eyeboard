"""Files a user can take away: a standalone HTML chart and a CSV table."""

import re

import pandas as pd
import plotly.graph_objects as go


def html_bytes(fig: go.Figure) -> bytes:
    """A self-contained HTML page of the chart: it opens offline, zoom included."""
    return fig.to_html(include_plotlyjs=True, full_html=True).encode("utf-8")


def csv_bytes(table: pd.DataFrame) -> bytes:
    """UTF-8 with a byte-order mark, so Excel shows accents correctly."""
    return table.to_csv(index=False).encode("utf-8-sig")


def png_config(name: str) -> dict:
    """Plotly toolbar settings: the camera icon saves a sharp, well-named PNG."""
    return {
        "toImageButtonOptions": {
            "format": "png",
            "scale": 2,
            "filename": file_stem(name),
        },
        "displaylogo": False,
    }


def file_stem(name: str) -> str:
    """A safe file name without extension (letters, digits, dashes, underscores)."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    return stem or "eyeboard"
