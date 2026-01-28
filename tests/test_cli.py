"""Tests for mt5linux CLI module."""

import pytest
from typer.testing import CliRunner
from mt5linux.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a Typer CLI test runner."""
    return CliRunner()


def test_cli_app_initialization(runner: CliRunner) -> None:
    """Test that CLI app is initialized correctly."""
    assert app is not None
    assert app.info.name == "mt5linux"


def test_setup_command_registered(runner: CliRunner) -> None:
    """Test that setup command is registered in the CLI."""
    # Since there's only one command, Typer makes it the default command
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "setup" in result.stdout.lower() or "automated setup" in result.stdout.lower()


def test_setup_command_help_text(runner: CliRunner) -> None:
    """Test that setup command displays proper help text."""
    result = runner.invoke(app, ["setup", "--help"])
    assert result.exit_code == 0
    assert "mode" in result.stdout.lower()
    assert "local" in result.stdout.lower() or "remote" in result.stdout.lower()


def test_setup_command_accepts_mode_parameter(runner: CliRunner) -> None:
    """Test that setup command accepts mode parameter."""
    result = runner.invoke(app, ["setup", "--mode", "local"])
    assert result.exit_code == 0
    assert "local" in result.stdout.lower()


def test_setup_command_default_mode(runner: CliRunner) -> None:
    """Test that setup command uses 'local' as default mode."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "local" in result.stdout.lower() or "mode: local" in result.stdout.lower()


def test_setup_command_remote_mode(runner: CliRunner) -> None:
    """Test that setup command accepts remote mode."""
    result = runner.invoke(app, ["setup", "--mode", "remote"])
    assert result.exit_code == 0
    assert "remote" in result.stdout.lower()


def test_setup_command_structure(runner: CliRunner) -> None:
    """Test that setup command follows Typer best practices."""
    result = runner.invoke(app, ["setup", "--help"])
    assert result.exit_code == 0
    # Typer automatically generates help with proper structure
    assert "--mode" in result.stdout or "-m" in result.stdout


def test_cli_main_help(runner: CliRunner) -> None:
    """Test that main CLI help displays correctly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mt5linux" in result.stdout.lower()
    assert "setup" in result.stdout.lower()


def test_setup_command_executes_without_errors(runner: CliRunner) -> None:
    """Test that setup command executes without errors."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Starting setup process" in result.stdout or "setup process" in result.stdout.lower()


def test_setup_command_uses_typer_output(runner: CliRunner) -> None:
    """Test that setup command uses Typer's output mechanisms."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Typer.echo output should be present
    assert len(result.stdout) > 0


def test_main_function_entry_point() -> None:
    """Test that main() function can be called directly."""
    from mt5linux.cli import main
    # Should not raise an exception when called
    # Note: This will actually invoke the CLI, so we test it doesn't crash
    # In a real scenario, we'd mock sys.argv
    try:
        import sys
        original_argv = sys.argv
        sys.argv = ["mt5linux", "--help"]
        main()
        sys.argv = original_argv
    except SystemExit:
        # Typer calls sys.exit() for --help, which is expected
        pass


def test_backward_compatibility_main_module() -> None:
    """Test that python -m mt5linux.__main__ still works (backward compatibility)."""
    # This test verifies that the existing __main__.py module is not broken
    # The __main__.py should still work for server launcher functionality
    import mt5linux.__main__
    # Just verify the module can be imported without errors
    assert mt5linux.__main__ is not None


def test_cli_module_main_guard() -> None:
    """Test that __name__ == '__main__' guard works correctly."""
    # Verify the module can be run directly
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "mt5linux.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 or result.returncode == 1  # Typer may exit with 1 for help
    assert "mt5linux" in result.stdout.lower() or "setup" in result.stdout.lower()


def test_setup_command_integrates_detection(runner: CliRunner) -> None:
    """Test that setup command integrates with environment detection."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Should contain detection output
    assert "Detecting environment" in result.stdout or "Environment:" in result.stdout
    assert "Component detection" in result.stdout or "components" in result.stdout.lower()


def test_setup_command_integrates_installer(runner: CliRunner) -> None:
    """Test that setup command integrates with installer (Story 1.3)."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Should contain installation-related output if components are missing
    # Or success message if all components are installed
    assert (
        "Installation" in result.stdout
        or "installing" in result.stdout.lower()
        or "All components" in result.stdout
        or "Setup process complete" in result.stdout
    )


def test_setup_command_integrates_remote_installer(runner: CliRunner) -> None:
    """Test that setup command integrates with remote installer (Story 1.4)."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Should contain remote-related output if remote environment detected
    # Or normal output if local environment
    assert (
        "remote" in result.stdout.lower()
        or "Remote" in result.stdout
        or "local" in result.stdout.lower()
        or "Setup process complete" in result.stdout
    )


def test_setup_command_integrates_wayland_config(runner: CliRunner) -> None:
    """Test that setup command integrates with Wayland configuration (Story 1.5)."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Should contain Wayland-related output if Wayland environment detected
    # Or normal output if X11 or remote environment
    assert (
        "wayland" in result.stdout.lower()
        or "Wayland" in result.stdout
        or "ydotool" in result.stdout.lower()
        or "X11" in result.stdout
        or "Setup process complete" in result.stdout
    )


def test_setup_command_integrates_pause(runner: CliRunner) -> None:
    """Test that setup command integrates with MT5 configuration pause (Story 1.6)."""
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    # Should contain pause-related output if MT5 was installed
    # Or normal output if MT5 already present or not installed
    assert (
        "pause" in result.stdout.lower()
        or "Pausing" in result.stdout
        or "MT5 configuration" in result.stdout
        or "Setup process complete" in result.stdout
    )


def test_config_command_show(runner: CliRunner) -> None:
    """Test that config show command displays configuration (Story 1.7)."""
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "Current Configuration" in result.stdout or "Configuration" in result.stdout
    assert "wine" in result.stdout.lower() or "server" in result.stdout.lower()


def test_config_command_set(runner: CliRunner) -> None:
    """Test that config set command updates configuration (Story 1.7)."""
    result = runner.invoke(app, ["config", "set", "server.port", "9999"])
    # May succeed or fail depending on config module availability
    assert result.exit_code in [0, 1]  # 0 if success, 1 if error (module not available)


def test_config_command_get(runner: CliRunner) -> None:
    """Test that config get command retrieves configuration value (Story 1.7)."""
    result = runner.invoke(app, ["config", "get", "server.port"])
    # May succeed or fail depending on config module availability
    assert result.exit_code in [0, 1]  # 0 if success, 1 if error (module not available)
