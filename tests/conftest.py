import pytest


@pytest.fixture(autouse=True)
def eyeboard_home(tmp_path, monkeypatch):
    """Give every test its own data folder: tests never touch the user's real files."""
    home = tmp_path / "eyeboard_home"
    monkeypatch.setenv("EYEBOARD_HOME", str(home))
    return home
