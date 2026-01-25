"""CLI entry point for mt5linux using Typer framework."""

from typer import Typer, Option, echo
from typing import Literal

try:
    from mt5linux.detection import detect_environment
except ImportError:
    detect_environment = None  # type: ignore

app: Typer = Typer(
    name="mt5linux",
    help="MetaTrader5 for Linux users - Automated setup and management",
)


@app.command()
def setup(
    mode: Literal["local", "remote"] = Option(
        "local",
        "--mode",
        "-m",
        help="Setup mode: 'local' for local desktop or 'remote' for remote server",
    ),
) -> None:
    """
    Automated setup command for mt5linux.

    Initiates the automated setup process with environment detection,
    dependency installation, and configuration.

    Args:
        mode: Setup mode - 'local' for local desktop or 'remote' for remote server
    """
    try:
        echo("Starting setup process...")
        echo(f"Setup mode: {mode}")

        # Environment detection (Story 1.2)
        if detect_environment is None:
            echo("Warning: Environment detection module not available")
            return

        echo("\n🔍 Detecting environment...")
        detection_result = detect_environment()

        # Validate detected environment matches user-specified mode
        if detection_result.environment_type != mode:
            echo(
                f"⚠️  Warning: Detected environment ({detection_result.environment_type}) "
                f"does not match specified mode ({mode})"
            )

        # Display detection results
        echo(f"  Environment: {detection_result.environment_type}")
        echo(f"  Display system: {detection_result.display_system}")

        # Display component detection results
        echo("\n📦 Component detection:")
        components = [
            ("Wine", detection_result.wine),
            ("System Python", detection_result.python_system),
            ("Windows Python", detection_result.python_windows),
            ("MetaTrader5", detection_result.mt5),
            ("rpyc", detection_result.rpyc),
        ]

        for name, info in components:
            if info.found:
                status = "✓ Found"
                details = f" ({info.path})"
                if info.version:
                    details += f" - {info.version}"
                echo(f"  {name}: {status}{details}")
            else:
                echo(f"  {name}: ✗ Not found")

        # Display installation plan if components are missing
        if detection_result.missing_components:
            echo(f"\n📋 Installation plan ({len(detection_result.missing_components)} components to install):")
            for i, step in enumerate(detection_result.installation_plan, 1):
                echo(f"  {i}. {step}")
        else:
            echo("\n✅ All components detected. No installation needed.")

        echo("\nSetup process initiated. Proceeding with installation plan...")
    except Exception as e:
        echo(f"Error during setup: {e}")
        raise


def main() -> None:
    """
    Entry point for CLI application.
    
    This function is called when the CLI is invoked directly via:
    - `python -m mt5linux.cli` 
    - Or when the entry point `mt5linux` is called after package installation.
    
    It delegates to the Typer app instance which handles command parsing and execution.
    """
    app()


if __name__ == "__main__":
    main()
