"""CLI entry point for mt5linux using Typer framework."""

import os
from typing import Literal, Optional

import typer
from typer import Argument, Option, Typer

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
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
    from mt5linux.setup.pause import (
        pause_for_mt5_configuration,
        verify_mt5_configuration,
    )
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

try:
    from mt5linux.monitoring.config_manager import NotificationConfigManager
except ImportError:
    NotificationConfigManager = None  # type: ignore

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
                    logger.debug(
                        f"Using saved Wine prefix from config: {saved_wine_prefix}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to load configuration: {e}, continuing with defaults"
                )

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
            echo(
                f"\n[blue]Installation plan[/blue] ({len(detection_result.missing_components)} components to install):"
            )
            for i, step in enumerate(detection_result.installation_plan, 1):
                echo(f"  {i}. {step}")

            # Install missing components (Story 1.3)
            if install_missing_components is None:
                echo("\n[yellow]Warning:[/yellow] Installation module not available")
                echo("Setup process initiated. Manual installation required.")
                return

            echo("\n[cyan]Installing missing components...[/cyan]")
            echo(f"  Using Wine prefix: [bold cyan]{wine_prefix}[/bold cyan]")
            installation_results = install_missing_components(
                detection_result, wine_prefix=wine_prefix
            )

            # Display installation results
            echo("\n[blue]Installation results:[/blue]")
            for result in installation_results:
                if result.installed:
                    echo(
                        f"  [bold green]{result.component}: Installed successfully[/bold green]"
                    )
                    if result.version:
                        echo(f"     Version: {result.version}")
                elif result.success and not result.installed:
                    echo(
                        f"  [yellow]{result.component}: Skipped (already installed)[/yellow]"
                    )
                else:
                    echo(
                        f"  [bold red]{result.component}: Installation failed[/bold red]"
                    )
                    if result.error:
                        echo(f"     Error: {result.error}")
                    if result.recovery_suggestion:
                        echo(f"     Suggestion: {result.recovery_suggestion}")

            # Check if all installations succeeded
            failed = [r for r in installation_results if not r.success]
            if failed:
                echo(
                    f"\n[yellow]Warning:[/yellow] {len(failed)} component(s) failed to install"
                )
                echo("You may need to install them manually or retry the setup.")
            else:
                echo(
                    "\n[bold green]All components installed successfully![/bold green]"
                )

            # Pause for MT5 configuration if MT5 was just installed successfully (Story 1.6)
            # AC #1: "When MT5 installation is complete" - implies successful installation
            # Check for both mt5-platform (executable) and mt5 (library) installations
            mt5_platform_installed = any(
                r.component == "mt5-platform" and r.installed and r.success
                for r in installation_results
            )
            mt5_library_installed = any(
                r.component == "mt5" and r.installed and r.success
                for r in installation_results
            )
            # We need the platform (executable) to be installed to launch MT5
            mt5_installed = mt5_platform_installed or mt5_library_installed
            if mt5_installed:
                if pause_for_mt5_configuration is None:
                    echo("\n[yellow]Warning:[/yellow] Pause module not available")
                else:
                    try:
                        # Re-detect MT5 after installation to get the correct path
                        # The original detection_result may not have MT5 path if it was just installed
                        logger.info(
                            "Re-detecting MT5 after installation for pause configuration..."
                        )
                        try:
                            from mt5linux.detection import detect_mt5

                            wine_path = (
                                detection_result.wine.path
                                if detection_result.wine.found
                                else None
                            )
                            # Use the wine prefix that was used for installation
                            mt5_info = detect_mt5(wine_path, wine_prefix)
                            if mt5_info.found and mt5_info.path:
                                # Update detection_result with the newly detected MT5 path
                                detection_result.mt5.found = True
                                detection_result.mt5.path = mt5_info.path
                                logger.info(f"MT5 re-detected at: {mt5_info.path}")
                            else:
                                logger.warning(
                                    "MT5 installation completed but re-detection failed"
                                )
                                # Try to get path from installation results (check both mt5-platform and mt5)
                                for result in installation_results:
                                    if (
                                        result.component == "mt5-platform"
                                        or result.component == "mt5"
                                    ) and result.path:
                                        detection_result.mt5.found = True
                                        detection_result.mt5.path = result.path
                                        logger.info(
                                            f"Using MT5 path from installation result: {result.path}"
                                        )
                                        break
                        except Exception as e:
                            logger.warning(
                                f"Error re-detecting MT5: {e}, using original detection_result"
                            )
                            logger.exception(e)

                        pause_result = pause_for_mt5_configuration(detection_result)
                        if pause_result.success and pause_result.resumed:
                            # Verify MT5 configuration after resume
                            if verify_mt5_configuration is None:
                                echo(
                                    "\n[yellow]Warning:[/yellow] Verification module not available"
                                )
                            else:
                                verification_result = verify_mt5_configuration(
                                    detection_result
                                )
                                if not verification_result.success:
                                    echo(
                                        f"\n[yellow]Warning:[/yellow] MT5 verification failed: {verification_result.error}"
                                    )
                                    if verification_result.recovery_suggestion:
                                        echo(
                                            f"   Suggestion: {verification_result.recovery_suggestion}"
                                        )
                                # Continue setup even if verification fails (non-blocking)
                        elif not pause_result.resumed:
                            # User cancelled or error occurred
                            if pause_result.error:
                                echo(
                                    f"\n[yellow]Warning:[/yellow] {pause_result.error}"
                                )
                            echo(
                                "Setup will continue, but MT5 may not be fully configured."
                            )
                    except KeyboardInterrupt:
                        echo("\n\n[yellow]Setup cancelled by user[/yellow]")
                        echo("You can resume setup later by running: mt5linux setup")
                        return
                    except Exception as e:
                        echo(
                            f"\n[yellow]Error during MT5 configuration pause:[/yellow] {e}"
                        )
                        echo("Setup will continue...")
                        logger.error(
                            f"Error during MT5 configuration pause: {e}", exc_info=True
                        )

            # Install remote components if needed (Story 1.4)
            if detection_result.environment_type == "remote":
                if install_remote_components is None:
                    echo(
                        "\n[yellow]Warning:[/yellow] Remote installer module not available"
                    )
                else:
                    echo("\n[cyan]Installing remote environment components...[/cyan]")
                    remote_results = install_remote_components(detection_result)

                    # Display remote installation results
                    if remote_results:
                        echo("\n[blue]Remote component installation results:[/blue]")
                        for result in remote_results:
                            if result.installed:
                                echo(
                                    f"  [bold green]{result.component}: Installed successfully[/bold green]"
                                )
                                if result.version:
                                    echo(f"     Version: {result.version}")
                            elif result.success and not result.installed:
                                echo(
                                    f"  [yellow]{result.component}: Skipped (already installed)[/yellow]"
                                )
                            else:
                                echo(
                                    f"  [bold red]{result.component}: Installation failed[/bold red]"
                                )
                                if result.error:
                                    echo(f"     Error: {result.error}")
                                if result.recovery_suggestion:
                                    echo(
                                        f"     Suggestion: {result.recovery_suggestion}"
                                    )

                        # Check if all remote installations succeeded
                        failed_remote = [r for r in remote_results if not r.success]
                        if failed_remote:
                            echo(
                                f"\n[yellow]Warning:[/yellow] {len(failed_remote)} remote component(s) failed to install"
                            )
                            if any("thinlinc" in r.component for r in failed_remote):
                                echo(
                                    "Note: ThinLinc may require manual installation. See error details above."
                                )
                        else:
                            echo(
                                "\n[bold green]All remote components installed successfully![/bold green]"
                            )
                            echo(
                                "[bold green]Remote GUI access configured. You can now access MT5 GUI via ThinLinc.[/bold green]"
                            )

            # Configure Wayland support if needed (Story 1.5)
            # Only configure if we're in local Wayland environment AND ydotool is not already configured
            # Note: Wine uses XWayland automatically on Wayland, so ydotool is only for automation
            if (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and not detection_result.ydotool.found
            ):
                if configure_wayland_support is None:
                    echo(
                        "\n[yellow]Warning:[/yellow] Wayland configuration module not available"
                    )
                else:
                    wayland_result = configure_wayland_support(detection_result)
                    if wayland_result.success:
                        if wayland_result.ydotool_configured:
                            echo(
                                "\n[bold green]Wayland support configured (ydotool available for automation)[/bold green]"
                            )
                        elif wayland_result.fallback_to_x11:
                            echo(
                                "\n[bold green]Falling back to X11 for GUI automation[/bold green]"
                            )
                        else:
                            echo(
                                "\n[yellow]Wayland configuration completed with warnings[/yellow]"
                            )
                    else:
                        echo("\n[yellow]Warning:[/yellow] Wayland configuration failed")
                        if wayland_result.error:
                            echo(f"   Error: {wayland_result.error}")
                        if wayland_result.recovery_suggestion:
                            echo(f"   Suggestion: {wayland_result.recovery_suggestion}")
            elif (
                detection_result.environment_type == "local"
                and detection_result.display_system == "wayland"
                and detection_result.ydotool.found
            ):
                echo(
                    "\n[bold green]Wayland support already configured (ydotool detected for automation)[/bold green]"
                )
        else:
            echo(
                "\n[bold green]All components detected. No installation needed.[/bold green]"
            )

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
    key: Optional[str] = Argument(
        None, help="Configuration key (for set/get, format: section.key)"
    ),
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
            echo("\n[wine]")
            if config.wine.prefix_path:
                echo(f"  prefix_path = {config.wine.prefix_path}")
            else:
                echo("  prefix_path = (not set)")
            echo("\n[server]")
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
                echo(
                    f"[bold red]Invalid key format:[/bold red] {key} (expected 'section.key')"
                )
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


# Notification commands sub-app (Story 4.5)
notification_app = Typer(help="Notification configuration commands")


@notification_app.command("setup")
def notification_setup(
    chat_id: str = Option(..., prompt="Telegram Chat ID", help="Telegram chat ID"),
    bot_token: str = Option(
        ..., prompt="Bot Token", hide_input=True, help="Telegram bot token"
    ),
) -> None:
    """Set up Telegram notifications (interactive wizard)."""
    if NotificationConfigManager is None:
        echo("[yellow]Notification configuration module not available[/yellow]")
        raise typer.Exit(1)

    manager = NotificationConfigManager()
    if manager.setup_telegram(chat_id=chat_id, bot_token=bot_token):
        echo("[bold green]Telegram setup successful[/bold green]")

        # Offer test
        if typer.confirm("Send test notification?"):
            success, msg = manager.test_telegram()
            if success:
                echo(f"[bold green]Test notification sent: {msg}[/bold green]")
            else:
                echo(f"[bold red]Test failed: {msg}[/bold red]")
    else:
        echo("[bold red]Telegram setup failed[/bold red]")
        raise typer.Exit(1)


@notification_app.command("test")
def notification_test() -> None:
    """Send a test notification."""
    if NotificationConfigManager is None:
        echo("[yellow]Notification configuration module not available[/yellow]")
        raise typer.Exit(1)

    manager = NotificationConfigManager()
    success, msg = manager.test_telegram()
    if success:
        echo(f"[bold green]{msg}[/bold green]")
    else:
        echo(f"[bold red]{msg}[/bold red]")
        raise typer.Exit(1)


@notification_app.command("status")
def notification_status() -> None:
    """Show notification configuration status."""
    if NotificationConfigManager is None:
        echo("[yellow]Notification configuration module not available[/yellow]")
        raise typer.Exit(1)

    manager = NotificationConfigManager()
    status = manager.get_telegram_status()

    echo("\n[blue]Telegram Configuration:[/blue]")
    echo(f"  Enabled: {status['enabled']}")
    echo(f"  Chat ID: {status['chat_id'] or 'Not configured'}")
    echo(
        f"  Bot Token: {'Configured' if status['bot_token_available'] else 'Not configured'}"
    )

    prefs = manager.get_preferences()
    echo("\n[blue]Notification Preferences:[/blue]")
    echo(f"  Failures: {'enabled' if prefs.failure_notifications else 'disabled'}")
    echo(
        f"  High Latency: {'enabled' if prefs.high_latency_notifications else 'disabled'}"
    )
    echo(
        f"  Trade Failures: {'enabled' if prefs.trade_failure_notifications else 'disabled'}"
    )
    echo(f"  Drawdown: {'enabled' if prefs.drawdown_notifications else 'disabled'}")
    echo(
        f"  Daily Reports: {'enabled' if prefs.daily_report_notifications else 'disabled'}"
    )
    if prefs.quiet_hours_enabled:
        echo(f"  Quiet Hours: {prefs.quiet_hours_start} - {prefs.quiet_hours_end}")
    else:
        echo("  Quiet Hours: disabled")


@notification_app.command("preferences")
def notification_preferences(
    show: bool = Option(False, "--show", help="Show current preferences"),
    failures: Optional[bool] = Option(None, help="Enable failure notifications"),
    latency: Optional[bool] = Option(None, help="Enable latency notifications"),
    trades: Optional[bool] = Option(None, help="Enable trade failure notifications"),
    drawdown: Optional[bool] = Option(None, help="Enable drawdown notifications"),
    reports: Optional[bool] = Option(None, help="Enable daily report notifications"),
    quiet_start: Optional[str] = Option(None, help="Quiet hours start (HH:MM)"),
    quiet_end: Optional[str] = Option(None, help="Quiet hours end (HH:MM)"),
) -> None:
    """Show or update notification preferences."""
    if NotificationConfigManager is None:
        echo("[yellow]Notification configuration module not available[/yellow]")
        raise typer.Exit(1)

    manager = NotificationConfigManager()

    # Check if any update options were provided
    has_updates = any(
        x is not None
        for x in [failures, latency, trades, drawdown, reports, quiet_start, quiet_end]
    )

    if show or not has_updates:
        # Show current preferences
        prefs = manager.get_preferences()
        echo("\n[blue]Notification Preferences:[/blue]")
        echo(f"  Failures: {'enabled' if prefs.failure_notifications else 'disabled'}")
        echo(
            f"  High Latency: {'enabled' if prefs.high_latency_notifications else 'disabled'}"
        )
        echo(
            f"  Trade Failures: {'enabled' if prefs.trade_failure_notifications else 'disabled'}"
        )
        echo(f"  Drawdown: {'enabled' if prefs.drawdown_notifications else 'disabled'}")
        echo(
            f"  Daily Reports: {'enabled' if prefs.daily_report_notifications else 'disabled'}"
        )
        if prefs.quiet_hours_enabled:
            echo(f"  Quiet Hours: {prefs.quiet_hours_start} - {prefs.quiet_hours_end}")
        else:
            echo("  Quiet Hours: disabled")
    else:
        # Update preferences
        updates = {}
        if failures is not None:
            updates["failure_notifications"] = failures
        if latency is not None:
            updates["high_latency_notifications"] = latency
        if trades is not None:
            updates["trade_failure_notifications"] = trades
        if drawdown is not None:
            updates["drawdown_notifications"] = drawdown
        if reports is not None:
            updates["daily_report_notifications"] = reports
        if quiet_start is not None:
            updates["quiet_hours_start"] = quiet_start
            updates["quiet_hours_enabled"] = True
        if quiet_end is not None:
            updates["quiet_hours_end"] = quiet_end
            updates["quiet_hours_enabled"] = True

        if manager.update_preferences(updates):
            echo("[bold green]Preferences updated[/bold green]")
        else:
            echo("[bold red]Failed to update preferences[/bold red]")
            raise typer.Exit(1)


# Register notification sub-app
app.add_typer(notification_app, name="notification")


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
