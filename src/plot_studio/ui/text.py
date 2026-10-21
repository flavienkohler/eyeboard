"""Helpers to display user-provided text safely in Streamlit."""

import re

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")


def escape_markdown(text: object) -> str:
    """Escape Markdown syntax so the text is displayed literally.

    Column names, file names and dashboard names come from user data. Rendered
    through ``st.markdown`` they could be read as formatting, math (``$``),
    emoji shortcodes (``:name:``) or links. Any ASCII punctuation may be
    backslash-escaped in Markdown, so escaping the special set is safe.
    """
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text))
