import importlib.util

import pytest


def test_ui_modules_import():
    if importlib.util.find_spec("streamlit") is None:
        pytest.skip("streamlit is not available in the current test interpreter")

    import plot_studio.app  # noqa: F401
    import plot_studio.ui.header  # noqa: F401
    import plot_studio.ui.sidebar  # noqa: F401
    import plot_studio.ui.tabs.compare  # noqa: F401
    import plot_studio.ui.tabs.dashboard  # noqa: F401
    import plot_studio.ui.tabs.plot_builder  # noqa: F401
    import plot_studio.ui.tabs.preview  # noqa: F401
    import plot_studio.ui.tabs.templates  # noqa: F401
