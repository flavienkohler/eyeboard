import importlib.util

import pytest


def test_ui_modules_import():
    if importlib.util.find_spec("streamlit") is None:
        pytest.skip("streamlit is not available in the current test interpreter")

    import eyeboard.app  # noqa: F401
    import eyeboard.ui.header  # noqa: F401
    import eyeboard.ui.sidebar  # noqa: F401
    import eyeboard.ui.tabs.compare  # noqa: F401
    import eyeboard.ui.tabs.dashboard  # noqa: F401
    import eyeboard.ui.tabs.dashboards_manager  # noqa: F401
    import eyeboard.ui.tabs.explore  # noqa: F401
    import eyeboard.ui.tabs.plot_builder  # noqa: F401
