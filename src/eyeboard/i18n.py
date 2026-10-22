"""Translation of the interface: English text is the key, a table gives the other languages.

``t("Upload CSV")`` returns the text in the current language and falls back to the
English text when a translation is missing, so a forgotten string is shown in
English instead of failing. Text with parts that change uses named fields:
``t("{count} rows", count=n)``.

The current language lives in a context variable, not in a global: Streamlit runs
each session in its own thread, and each script run sets the language of its
session first (``set_language``), so two sessions never see each other's choice.
"""

from contextvars import ContextVar

from eyeboard.translations.fr import FR

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English", "fr": "Français"}
TRANSLATIONS: dict[str, dict[str, str]] = {"fr": FR}

_current: ContextVar[str] = ContextVar("eyeboard_language", default=DEFAULT_LANGUAGE)


def set_language(code: str) -> None:
    """Use this language for the rest of the current script run."""
    _current.set(code if code in LANGUAGES else DEFAULT_LANGUAGE)


def current_language() -> str:
    """The language code in use (also useful as part of a cache key)."""
    return _current.get()


def t(text: str, /, **values: object) -> str:
    """Translate ``text`` and fill its named fields, if any."""
    translated = TRANSLATIONS.get(_current.get(), {}).get(text, text)
    return translated.format(**values) if values else translated
