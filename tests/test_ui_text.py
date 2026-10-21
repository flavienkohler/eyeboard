import pytest

from plot_studio.ui.text import escape_markdown


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain", "plain"),
        ("a*b*", r"a\*b\*"),
        ("price $ vs $ cost", r"price \$ vs \$ cost"),
        ("[x](http://example.com)", r"\[x\]\(http\://example\.com\)"),
        ("<img src=x>", r"\<img src=x\>"),
        ("`code`", r"\`code\`"),
        (":smile:", r"\:smile\:"),
        ("temp_m1_12h", r"temp\_m1\_12h"),
        ("back\\slash", "back\\\\slash"),
    ],
)
def test_escape_markdown_neutralises_syntax(raw, expected):
    assert escape_markdown(raw) == expected


def test_escape_markdown_accepts_non_strings():
    assert escape_markdown(12) == "12"
    assert escape_markdown(None) == "None"
