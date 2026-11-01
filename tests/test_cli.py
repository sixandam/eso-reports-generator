"""
Tests for CLI entrypoint and argument handling.
Ensures that the CLI has no flags and launches the graphical interface directly.
"""

from click.testing import CliRunner
from eso_reports.cli import main
import eso_reports.cli as cli_module


def test_cli_help():
    """Verify that --help shows no CLI flags and mentions GUI launch."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Launch the ESO Report Generator GUI" in result.output
    # Assert no flags exist
    assert "--start-date" not in result.output
    assert "--end-date" not in result.output
    assert "--output" not in result.output
    assert "--demo" not in result.output
    assert "--reauth" not in result.output
    assert "--last-month" not in result.output
    assert "--headless" not in result.output
    assert "--gui" not in result.output


def test_cli_launches_gui(monkeypatch):
    """Verify executing main with no arguments launches the GUI."""
    called = False

    def mock_launch():
        nonlocal called
        called = True

    monkeypatch.setattr(cli_module, "launch_gui", mock_launch)
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert called is True


def test_cli_rejects_flags():
    """Verify that any CLI flags are rejected."""
    runner = CliRunner()
    for flag in ["--start-date", "--output", "--demo", "--last-month", "--headless"]:
        result = runner.invoke(main, [flag])
        assert result.exit_code != 0
        assert "no such option" in result.output.lower()
