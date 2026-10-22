import ast
import threading
from pathlib import Path
from string import Formatter

import pytest

from eyeboard.i18n import LANGUAGES, TRANSLATIONS, current_language, set_language, t

SRC = Path(__file__).resolve().parents[1] / "src" / "eyeboard"


@pytest.fixture(autouse=True)
def english_again():
    yield
    set_language("en")


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def _source_files():
    return [p for p in SRC.rglob("*.py") if "translations" not in p.parts]


def _translated_literals() -> set[str]:
    """First arguments of every t("...") call in the source."""
    found = set()
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
    return found


def _all_literals() -> set[str]:
    found = set()
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add(node.value)
    return found


def test_english_is_the_default_and_fields_are_filled():
    assert t("Plot") == "Plot"
    assert t("{count} rows", count=3) == "3 rows"
    assert t("Page {n:,}", n=1234) == "Page 1,234"
    assert current_language() == "en"


def test_a_missing_translation_falls_back_to_english():
    set_language("fr")

    assert t("A sentence nobody translated") == "A sentence nobody translated"
    assert t("A {x} nobody translated", x=1) == "A 1 nobody translated"


def test_an_unknown_language_is_english():
    set_language("xx")

    assert current_language() == "en"


def test_the_language_of_one_thread_is_not_seen_by_another():
    set_language("fr")
    seen = []

    thread = threading.Thread(target=lambda: seen.append(current_language()))
    thread.start()
    thread.join()

    assert seen == ["en"] and current_language() == "fr"


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "en"])
def test_every_translated_text_of_the_source_has_a_translation(code):
    missing = sorted(_translated_literals() - set(TRANSLATIONS[code]))

    assert missing == [], f"Add these to translations/{code}.py: {missing}"


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "en"])
def test_translations_that_nothing_uses_are_reported(code):
    used = _translated_literals() | _all_literals()
    unused = sorted(set(TRANSLATIONS[code]) - used)

    assert unused == [], f"Remove from translations/{code}.py: {unused}"


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "en"])
def test_a_translation_keeps_the_fields_of_the_english_text(code):
    for english, translated in TRANSLATIONS[code].items():
        assert _fields(english) == _fields(translated), english


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "en"])
def test_column_match_notes_start_with_the_translation_of_matched(code):
    set_language(code)
    prefix = t("Matched ")
    notes = [
        t("Matched X column '{requested}' -> '{found}'", requested="a", found="b"),
        t("Matched Y column '{requested}' -> '{found}'", requested="a", found="b"),
        t("Matched Y2 column '{requested}' -> '{found}'", requested="a", found="b"),
    ]

    assert all(note.startswith(prefix) for note in notes)
