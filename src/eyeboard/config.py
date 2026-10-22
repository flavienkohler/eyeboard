"""Project-wide configuration constants."""

from pathlib import Path

import plotly.express as px

LOGO_PATH = Path(__file__).parent / "assets" / "logo.svg"
APP_PAGE_TITLE = "EyeBoard"
APP_PAGE_ICON = str(LOGO_PATH)
APP_LAYOUT = "wide"
APP_HEADER_TITLE = "EyeBoard"
APP_HEADER_SUBTITLE = (
    "Explore time-series CSV files, build reusable dashboards, compare runs."
)

REPO_URL = "https://github.com/flavienkohler/eyeboard"
ISSUES_URL = f"{REPO_URL}/issues/new/choose"
AUTHOR_NAME = "Flavien Kohler"
AUTHOR_GITHUB_URL = "https://github.com/flavienkohler"
AUTHOR_LINKEDIN_URL: str | None = "https://www.linkedin.com/in/flavien-kohler"
ABOUT_BUTTON_COLOR = "#6ed59a"

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
