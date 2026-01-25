"""CLI entry point for mt5linux using Typer framework."""

from typer import Typer, Option, echo
from typing import Literal

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from mt5linux.detection import detect_environment
except ImportError:
    detect_environment = None  # type: ignore

try:
    from mt5linux.setup.installer import install_missing_components
except ImportError:
    install_missing_components = None  # type: ignore

try:
    from mt5linux.setup.remote_installer import install_remote_components
except ImportError:
    install_remote_components = None  # type: ignore

try:
    from mt5linux.setup.wayland_config import configure_wayland_support
except ImportError:
    configure_wayland_support = None  # type: ignore

try:
    from mt5linux.setup.pause import pause_for_mt5_configuration, verify_mt5_configuration
except ImportError:
    pause_for_mt5_configuration = None  # type: ignore
    verify_mt5_configuration = None  # type: ignore

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

            # Pause for MT5 configuration if MT5 was just installed successfully (Story 1.6)
            # AC #1: "When MT5 installation is complete" - implies successful installation
            mt5_installed = any(
                r.component == "mt5" and r.installed and r.success
                for r in installation_results
            )
            if mt5_installed:
                if pause_for_mt5_configuration is None:
                    echo("\n⚠️  Warning: Pause module not available")
                else:
                    try:
                        pause_result = pause_for_mt5_configuration(detection_result)
                        if pause_result.success and pause_result.resumed:
                            # Verify MT5 configuration after resume
                            if verify_mt5_configuration is None:
                                echo("\n⚠️  Warning: Verification module not available")
                            else:
                                verification_result = verify_mt5_configuration(detection_result)
                                if not verification_result.success:
                                    echo(f"\n⚠️  Warning: MT5 verification failed: {verification_result.error}")
                                    if verification_result.recovery_suggestion:
                                        echo(f"   Suggestion: {verification_result.recovery_suggestion}")
                                # Continue setup even if verification fails (non-blocking)
                        elif not pause_result.resumed:
                            # User cancelled or error occurred
                            if pause_result.error:
                                echo(f"\n⚠️  Warning: {pause_result.error}")
                            echo("Setup will continue, but MT5 may not be fully configured.")
                    except KeyboardInterrupt:
                        echo("\n\n⚠️  Setup cancelled by user")
                        echo("You can resume setup later by running: mt5linux setup")
                        return
                    except Exception as e:
                        echo(f"\n⚠️  Error during MT5 configuration pause: {e}")
                        echo("Setup will continue...")
                        logger.error(f"Error during MT5 configuration pause: {e}", exc_info=True)

            # Install remote components if needed (Story 1.4)
            if detection_result.environment_type == "remote":
                if install_remote_components is None:
                    echo("\n⚠️  Warning: Remote installer module not available")
                else:
                    echo("\n🌐 Installing remote environment components...")
                    remote_results = install_remote_components(detection_result)

                    # Display remote installation results
                    if remote_results:
                        echo("\n📊 Remote component installation results:")
                        for result in remote_results:
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

                        # Check if all remote installations succeeded
                        failed_remote = [r for r in remote_results if not r.success]
                        if failed_remote:
                            echo(f"\n⚠️  Warning: {len(failed_remote)} remote component(s) failed to install")
                            if any("thinlinc" in r.component for r in failed_remote):
                                echo("Note: ThinLinc may require manual installation. See error details above.")
                        else:
                            echo("\n✅ All remote components installed successfully!")
                            echo("✅ Remote GUI access configured. You can now access MT5 GUI via ThinLinc.")

            # Configure Wayland support if needed (Story 1.5)
            # Only configure if we're in local Wayland environment AND xyphir is not already configured
            if (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and not detection_result.xyphir.found
            ):
                if configure_wayland_support is None:
                    echo("\n⚠️  Warning: Wayland configuration module not available")
                else:
                    wayland_result = configure_wayland_support(detection_result)
                    if wayland_result.success:
                        if wayland_result.xyphir_configured:
                            echo("\n✅ Wayland support configured with xyphir")
                        elif wayland_result.fallback_to_x11:
                            echo("\n✅ Falling back to X11 for GUI automation")
                        else:
                            echo("\n⚠️  Wayland configuration completed with warnings")
                    else:
                        echo("\n⚠️  Warning: Wayland configuration failed")
                        if wayland_result.error:
                            echo(f"   Error: {wayland_result.error}")
                        if wayland_result.recovery_suggestion:
                            echo(f"   Suggestion: {wayland_result.recovery_suggestion}")
            elif (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and detection_result.xyphir.found
            ):
                echo("\n✅ Wayland support already configured (xyphir detected)")
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
