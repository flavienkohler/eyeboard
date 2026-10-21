"""Command line entry point: ``eyeboard`` starts the app in the browser."""

import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli

SCRIPT = Path(__file__).with_name("streamlit_app.py")


def build_streamlit_args(extra_args: list[str]) -> list[str]:
    """Return the ``streamlit`` command line that starts the EyeBoard script.

    Extra arguments are passed through, so ``eyeboard --server.port 8600`` works.
    """
    return [
        "streamlit",
        "run",
        str(SCRIPT),
        "--browser.gatherUsageStats=false",
        *extra_args,
    ]


def main() -> None:
    """Start EyeBoard."""
    sys.argv = build_streamlit_args(sys.argv[1:])
    sys.exit(streamlit_cli.main())
