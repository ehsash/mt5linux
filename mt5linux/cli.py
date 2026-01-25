"""CLI entry point for mt5linux using Typer framework."""

from typer import Typer, Option, echo
from typing import Literal

try:
    from mt5linux.detection import detect_environment
except ImportError:
    detect_environment = None  # type: ignore

try:
    from mt5linux.setup.installer import install_missing_components
except ImportError:
    install_missing_components = None  # type: ignore

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

            # Install missing components (Story 1.3)
            if install_missing_components is None:
                echo("\n⚠️  Warning: Installation module not available")
                echo("Setup process initiated. Manual installation required.")
                return

            echo("\n🔧 Installing missing components...")
            installation_results = install_missing_components(detection_result)

            # Display installation results
            echo("\n📊 Installation results:")
            for result in installation_results:
                if result.installed:
                    echo(f"  ✅ {result.component}: Installed successfully")
                    if result.version:
                        echo(f"     Version: {result.version}")
                elif result.success and not result.installed:
                    echo(f"  ⏭️  {result.component}: Skipped (already installed)")
                else:
                    echo(f"  ❌ {result.component}: Installation failed")
                    if result.error:
                        echo(f"     Error: {result.error}")
                    if result.recovery_suggestion:
                        echo(f"     Suggestion: {result.recovery_suggestion}")

            # Check if all installations succeeded
            failed = [r for r in installation_results if not r.success]
            if failed:
                echo(f"\n⚠️  Warning: {len(failed)} component(s) failed to install")
                echo("You may need to install them manually or retry the setup.")
            else:
                echo("\n✅ All components installed successfully!")
        else:
            echo("\n✅ All components detected. No installation needed.")

        echo("\nSetup process complete!")
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
