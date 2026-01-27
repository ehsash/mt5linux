"""CLI entry point for mt5linux using Typer framework."""

import os
import typer
from typer import Typer, Option, Argument
from typing import Literal, Optional

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
except ImportError:
    Console = None  # type: ignore
    Table = None  # type: ignore
    Panel = None  # type: ignore

# Initialize rich console if available
_console = Console() if Console else None

# Fallback echo function
def echo(message: str) -> None:
    """Echo function that uses rich if available, otherwise print."""
    if _console:
        _console.print(message)
    else:
        print(message)

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

try:
    from mt5linux.config import (
        extract_wine_prefix_from_detection,
        get_config,
        load_config,
        save_config,
        update_config,
    )
except ImportError:
    extract_wine_prefix_from_detection = None  # type: ignore
    get_config = None  # type: ignore
    load_config = None  # type: ignore
    save_config = None  # type: ignore
    update_config = None  # type: ignore

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

        # Load existing configuration (Story 1.7) - AC #2: use saved Wine prefix
        saved_wine_prefix = None
        if load_config is not None:
            try:
                config = load_config()
                saved_wine_prefix = config.wine.prefix_path
                if saved_wine_prefix:
                    logger.debug(f"Using saved Wine prefix from config: {saved_wine_prefix}")
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}, continuing with defaults")

        # Environment detection (Story 1.2) - AC #2: use saved Wine prefix if available
        if detect_environment is None:
            echo("Warning: Environment detection module not available")
            return

        echo("\n[cyan]Detecting environment...[/cyan]")
        detection_result = detect_environment(wine_prefix=saved_wine_prefix)

        # Validate detected environment matches user-specified mode
        if detection_result.environment_type != mode:
            echo(
                f"[yellow]Warning:[/yellow] Detected environment ({detection_result.environment_type}) "
                f"does not match specified mode ({mode})"
            )

        # Display detection results
        echo(f"  Environment: {detection_result.environment_type}")
        echo(f"  Display system: {detection_result.display_system}")
        
        # Determine and display Wine prefix
        wine_prefix = saved_wine_prefix
        if not wine_prefix:
            # Default to .mt5 in current directory
            wine_prefix = os.path.join(os.getcwd(), ".mt5")
        echo(f"  Wine prefix: [bold cyan]{wine_prefix}[/bold cyan]")

        # Display component detection results
        echo("\n[blue]Component detection:[/blue]")
        components = [
            ("Wine", detection_result.wine),
            ("System Python", detection_result.python_system),
            ("Windows Python", detection_result.python_windows),
            ("MetaTrader5", detection_result.mt5),
            ("rpyc", detection_result.rpyc),
        ]

        for name, info in components:
            if info.found:
                status = "[bold green]Found[/bold green]"
                details = f" ({info.path})"
                if info.version:
                    details += f" - {info.version}"
                echo(f"  {name}: {status}{details}")
            else:
                echo(f"  {name}: [bold red]Not found[/bold red]")

        # Display installation plan if components are missing
        if detection_result.missing_components:
            echo(f"\n[blue]Installation plan[/blue] ({len(detection_result.missing_components)} components to install):")
            for i, step in enumerate(detection_result.installation_plan, 1):
                echo(f"  {i}. {step}")

            # Install missing components (Story 1.3)
            if install_missing_components is None:
                echo("\n[yellow]Warning:[/yellow] Installation module not available")
                echo("Setup process initiated. Manual installation required.")
                return

            echo(f"\n[cyan]Installing missing components...[/cyan]")
            echo(f"  Using Wine prefix: [bold cyan]{wine_prefix}[/bold cyan]")
            installation_results = install_missing_components(detection_result, wine_prefix=wine_prefix)

            # Display installation results
            echo("\n[blue]Installation results:[/blue]")
            for result in installation_results:
                if result.installed:
                    echo(f"  [bold green]{result.component}: Installed successfully[/bold green]")
                    if result.version:
                        echo(f"     Version: {result.version}")
                elif result.success and not result.installed:
                    echo(f"  [yellow]{result.component}: Skipped (already installed)[/yellow]")
                else:
                    echo(f"  [bold red]{result.component}: Installation failed[/bold red]")
                    if result.error:
                        echo(f"     Error: {result.error}")
                    if result.recovery_suggestion:
                        echo(f"     Suggestion: {result.recovery_suggestion}")

            # Check if all installations succeeded
            failed = [r for r in installation_results if not r.success]
            if failed:
                echo(f"\n[yellow]Warning:[/yellow] {len(failed)} component(s) failed to install")
                echo("You may need to install them manually or retry the setup.")
            else:
                echo("\n[bold green]All components installed successfully![/bold green]")

            # Pause for MT5 configuration if MT5 was just installed successfully (Story 1.6)
            # AC #1: "When MT5 installation is complete" - implies successful installation
            mt5_installed = any(
                r.component == "mt5" and r.installed and r.success
                for r in installation_results
            )
            if mt5_installed:
                if pause_for_mt5_configuration is None:
                    echo("\n[yellow]Warning:[/yellow] Pause module not available")
                else:
                    try:
                        pause_result = pause_for_mt5_configuration(detection_result)
                        if pause_result.success and pause_result.resumed:
                            # Verify MT5 configuration after resume
                            if verify_mt5_configuration is None:
                                echo("\n[yellow]Warning:[/yellow] Verification module not available")
                            else:
                                verification_result = verify_mt5_configuration(detection_result)
                                if not verification_result.success:
                                    echo(f"\n[yellow]Warning:[/yellow] MT5 verification failed: {verification_result.error}")
                                    if verification_result.recovery_suggestion:
                                        echo(f"   Suggestion: {verification_result.recovery_suggestion}")
                                # Continue setup even if verification fails (non-blocking)
                        elif not pause_result.resumed:
                            # User cancelled or error occurred
                            if pause_result.error:
                                echo(f"\n[yellow]Warning:[/yellow] {pause_result.error}")
                            echo("Setup will continue, but MT5 may not be fully configured.")
                    except KeyboardInterrupt:
                        echo("\n\n[yellow]Setup cancelled by user[/yellow]")
                        echo("You can resume setup later by running: mt5linux setup")
                        return
                    except Exception as e:
                        echo(f"\n[yellow]Error during MT5 configuration pause:[/yellow] {e}")
                        echo("Setup will continue...")
                        logger.error(f"Error during MT5 configuration pause: {e}", exc_info=True)

            # Install remote components if needed (Story 1.4)
            if detection_result.environment_type == "remote":
                if install_remote_components is None:
                    echo("\n[yellow]Warning:[/yellow] Remote installer module not available")
                else:
                    echo("\n[cyan]Installing remote environment components...[/cyan]")
                    remote_results = install_remote_components(detection_result)

                    # Display remote installation results
                    if remote_results:
                        echo("\n[blue]Remote component installation results:[/blue]")
                        for result in remote_results:
                            if result.installed:
                                echo(f"  [bold green]{result.component}: Installed successfully[/bold green]")
                                if result.version:
                                    echo(f"     Version: {result.version}")
                            elif result.success and not result.installed:
                                echo(f"  [yellow]{result.component}: Skipped (already installed)[/yellow]")
                            else:
                                echo(f"  [bold red]{result.component}: Installation failed[/bold red]")
                                if result.error:
                                    echo(f"     Error: {result.error}")
                                if result.recovery_suggestion:
                                    echo(f"     Suggestion: {result.recovery_suggestion}")

                        # Check if all remote installations succeeded
                        failed_remote = [r for r in remote_results if not r.success]
                        if failed_remote:
                            echo(f"\n[yellow]Warning:[/yellow] {len(failed_remote)} remote component(s) failed to install")
                            if any("thinlinc" in r.component for r in failed_remote):
                                echo("Note: ThinLinc may require manual installation. See error details above.")
                        else:
                            echo("\n[bold green]All remote components installed successfully![/bold green]")
                            echo("[bold green]Remote GUI access configured. You can now access MT5 GUI via ThinLinc.[/bold green]")

            # Configure Wayland support if needed (Story 1.5)
            # Only configure if we're in local Wayland environment AND xyphir is not already configured
            if (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and not detection_result.xyphir.found
            ):
                if configure_wayland_support is None:
                    echo("\n[yellow]Warning:[/yellow] Wayland configuration module not available")
                else:
                    wayland_result = configure_wayland_support(detection_result)
                    if wayland_result.success:
                        if wayland_result.xyphir_configured:
                            echo("\n[bold green]Wayland support configured with xyphir[/bold green]")
                        elif wayland_result.fallback_to_x11:
                            echo("\n[bold green]Falling back to X11 for GUI automation[/bold green]")
                        else:
                            echo("\n[yellow]Wayland configuration completed with warnings[/yellow]")
                    else:
                        echo("\n[yellow]Warning:[/yellow] Wayland configuration failed")
                        if wayland_result.error:
                            echo(f"   Error: {wayland_result.error}")
                        if wayland_result.recovery_suggestion:
                            echo(f"   Suggestion: {wayland_result.recovery_suggestion}")
            elif (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and detection_result.xyphir.found
            ):
                echo("\n[bold green]Wayland support already configured (xyphir detected)[/bold green]")
        else:
            echo("\n[bold green]All components detected. No installation needed.[/bold green]")

        # Save configuration after successful setup (Story 1.7)
        if save_config is not None and extract_wine_prefix_from_detection is not None:
            try:
                config = get_config()
                # Extract Wine prefix from detection results
                wine_prefix = extract_wine_prefix_from_detection(detection_result)
                if wine_prefix:
                    config.wine.prefix_path = wine_prefix
                # Server defaults are already set in Config defaults
                if save_config(config):
                    echo("\n[bold green]Configuration saved successfully[/bold green]")
                    logger.info("Configuration saved after setup completion")
                else:
                    logger.warning("Failed to save configuration (non-blocking)")
            except Exception as e:
                logger.warning(f"Failed to save configuration: {e} (non-blocking)")
                # Don't block setup completion if config save fails

        echo("\nSetup process complete!")
    except Exception as e:
        echo(f"Error during setup: {e}")
        raise


@app.command()
def config(
    action: str = Argument(..., help="Action: show, set, or get"),
    key: Optional[str] = Argument(None, help="Configuration key (for set/get, format: section.key)"),
    value: Optional[str] = Argument(None, help="Configuration value (for set)"),
) -> None:
    """
    Manage mt5linux configuration.

    Actions:
    - show: Display current configuration
    - set <key> <value>: Update configuration value (e.g., "wine.prefix_path" "/path/to/prefix")
    - get <key>: Get specific configuration value (e.g., "server.port")
    """
    if get_config is None or update_config is None:
        echo("[yellow]Configuration module not available[/yellow]")
        return

    try:
        if action == "show":
            config = get_config()
            echo("\n[blue]Current Configuration:[/blue]")
            echo("=" * 50)
            echo(f"\n[wine]")
            if config.wine.prefix_path:
                echo(f"  prefix_path = {config.wine.prefix_path}")
            else:
                echo("  prefix_path = (not set)")
            echo(f"\n[server]")
            echo(f"  host = {config.server.host}")
            echo(f"  port = {config.server.port}")
            echo("")

        elif action == "set":
            if not key or not value:
                echo("[bold red]Error:[/bold red] 'set' requires both key and value")
                echo("Usage: mt5linux config set <key> <value>")
                echo("Example: mt5linux config set wine.prefix_path /path/to/prefix")
                return

            if update_config(key, value):
                echo(f"[bold green]Configuration updated:[/bold green] {key} = {value}")
            else:
                echo(f"[bold red]Failed to update configuration:[/bold red] {key}")
                echo("Check logs for details")

        elif action == "get":
            if not key:
                echo("[bold red]Error:[/bold red] 'get' requires a key")
                echo("Usage: mt5linux config get <key>")
                echo("Example: mt5linux config get server.port")
                return

            config = get_config()
            parts = key.split(".")
            if len(parts) != 2:
                echo(f"[bold red]Invalid key format:[/bold red] {key} (expected 'section.key')")
                return

            section, field_name = parts
            if section == "wine" and field_name == "prefix_path":
                echo(config.wine.prefix_path or "(not set)")
            elif section == "server" and field_name == "host":
                echo(config.server.host)
            elif section == "server" and field_name == "port":
                echo(config.server.port)
            else:
                echo(f"[bold red]Unknown configuration key:[/bold red] {key}")

        else:
            echo(f"[bold red]Unknown action:[/bold red] {action}")
            echo("Valid actions: show, set, get")

    except Exception as e:
        echo(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Error in config command: {e}", exc_info=True)


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
