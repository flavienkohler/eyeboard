"""Command line entry point: ``eyeboard`` starts the app in the browser."""

import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli

SCRIPT = Path(__file__).with_name("streamlit_app.py")


def build_streamlit_args(extra_args: list[str]) -> list[str]:
    """Return the ``streamlit`` command line that starts the EyeBoard script.

    Extra arguments are passed through, so ``eyeboard --server.port 8600`` works.
    They come last, so they override the defaults set here: the app listens on this
    machine only (it has no login and keeps your files, so it must not be reachable
    from the network unless asked for, e.g. ``--server.address 0.0.0.0``).
    """
    return [
        "streamlit",
        "run",
        str(SCRIPT),
        "--browser.gatherUsageStats=false",
        "--server.address=localhost",
        *extra_args,
    ]


def main() -> None:
    """Start EyeBoard."""
    sys.argv = build_streamlit_args(sys.argv[1:])
    sys.exit(streamlit_cli.main())
