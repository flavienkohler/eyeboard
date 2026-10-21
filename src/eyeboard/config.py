"""Project-wide configuration constants."""

import plotly.express as px

APP_PAGE_TITLE = "EyeBoard"
APP_PAGE_ICON = ":chart_with_upwards_trend:"
APP_LAYOUT = "wide"
APP_HEADER_TITLE = "EyeBoard"
APP_HEADER_SUBTITLE = (
    "Build reusable dashboards for CSV data without saving plot snapshots."
)

CANDIDATE_SEPARATORS = [",", ";", "\t", "|"]
ENCODING_OPTIONS = {
    "Auto-detect": None,
    "UTF-8": "utf-8",
    "Windows-1252 (Excel)": "cp1252",
    "UTF-16": "utf-16",
}
DATE_KEYWORDS = ("date", "time", "datum", "zeit", "datetime")
DATE_PARSE_MODES = ["Auto-detect", "Day-first", "Month-first"]
RECENT_CSV_LIMIT = 10

PLOT_TYPES = ["Line", "Scatter", "Bar", "Area"]
THEMES = [
    "plotly",
    "plotly_white",
    "plotly_dark",
    "ggplot2",
    "seaborn",
    "simple_white",
    "none",
]
DEFAULT_SERIES_COLORS = px.colors.qualitative.Plotly
