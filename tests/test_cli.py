import eyeboard.cli as cli


def test_the_script_started_by_the_command_exists_and_runs_the_app():
    assert cli.SCRIPT.name == "streamlit_app.py" and cli.SCRIPT.exists()
    assert "from eyeboard.app import main" in cli.SCRIPT.read_text(encoding="utf-8")


def test_the_command_line_runs_the_script_and_passes_extra_arguments():
    args = cli.build_streamlit_args(["--server.port", "8600"])

    assert args[:3] == ["streamlit", "run", str(cli.SCRIPT)]
    assert "--browser.gatherUsageStats=false" in args
    assert args[-2:] == ["--server.port", "8600"]


def test_main_hands_over_to_streamlit(monkeypatch):
    seen = {}

    def fake_streamlit_main():
        import sys

        seen["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(cli.streamlit_cli, "main", fake_streamlit_main)
    monkeypatch.setattr("sys.argv", ["eyeboard", "--server.headless", "true"])

    try:
        cli.main()
    except SystemExit as exit_:
        assert exit_.code == 0

    assert seen["argv"][:2] == ["streamlit", "run"]
    assert seen["argv"][-2:] == ["--server.headless", "true"]
