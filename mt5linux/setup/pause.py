"""Pause/resume mechanism for MT5 configuration during setup."""

import os
import socket
import time
from dataclasses import dataclass
from typing import Optional

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from typer import prompt
except ImportError:
    prompt = input  # type: ignore

try:
    from rich.console import Console
except ImportError:
    Console = None  # type: ignore

# Initialize rich console if available
_console = Console() if Console else None

# Fallback echo function
def echo(message: str) -> None:
    """Echo function that uses rich if available, otherwise print."""
    if _console:
        _console.print(message)
    else:
        print(message)

from mt5linux.detection import DetectionResult


@dataclass
class PauseResult:
    """Result of a pause operation."""

    success: bool
    resumed: bool
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of MT5 configuration verification."""

    success: bool
    mt5_accessible: bool
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


def get_mt5_gui_instructions(detection_result: DetectionResult) -> str:
    """
    Generate MT5 GUI access instructions based on environment.

    Args:
        detection_result: Current environment detection results

    Returns:
        Formatted string with step-by-step instructions for accessing MT5 GUI
    """
    logger.debug("Generating MT5 GUI access instructions")
    instructions = []

    # Get MT5 path and Wine prefix
    mt5_path = detection_result.mt5.path if detection_result.mt5.found else "MT5 executable"
    wine_path = detection_result.wine.path if detection_result.wine.found else "wine"
    
    # Extract Wine prefix from MT5 path if available
    wine_prefix = None
    if detection_result.mt5.found and detection_result.mt5.path:
        # Try to extract prefix (e.g., ~/.wine from ~/.wine/drive_c/...)
        mt5_dir = os.path.dirname(detection_result.mt5.path)
        if "drive_c" in mt5_dir:
            # Go up to find Wine prefix (drive_c is inside prefix)
            prefix_candidate = os.path.dirname(mt5_dir)
            if os.path.isdir(prefix_candidate):
                wine_prefix = prefix_candidate
        # Fallback to common prefixes
        if not wine_prefix:
            common_prefixes = [
                os.path.join(os.getcwd(), ".mt5"),  # Default mt5linux prefix
                os.path.expanduser("~/.wine"),
                os.path.join(os.getcwd(), ".wine"),
            ]
            for prefix in common_prefixes:
                if os.path.isdir(prefix):
                    wine_prefix = prefix
                    break

    if detection_result.environment_type == "remote":
        # Remote environment instructions
        instructions.append("**Remote Environment - Access MT5 via ThinLinc:**")
        instructions.append("")
        instructions.append("1. Connect to this server using ThinLinc client:")
        # Get connection details (AC #3: provide ThinLinc connection details)
        try:
            hostname = socket.gethostname()
            fqdn = socket.getfqdn()
            # Try to get IP address
            ip_address = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
            except Exception:
                pass  # IP address not available
            
            if ip_address:
                instructions.append(f"   - Server hostname: {hostname} ({fqdn})")
                instructions.append(f"   - Server IP address: {ip_address}")
                instructions.append(f"   - Use ThinLinc client to connect to: {hostname} or {ip_address}")
            else:
                instructions.append(f"   - Server hostname: {hostname} ({fqdn})")
                instructions.append(f"   - Use ThinLinc client to connect to: {hostname}")
        except Exception:
            instructions.append("   - Use your ThinLinc client to connect to this server")
        if detection_result.thinlinc.found and detection_result.thinlinc.path:
            instructions.append(f"   - ThinLinc is installed at: {detection_result.thinlinc.path}")
        instructions.append("   - Default ThinLinc port: 22 (SSH) or 443 (HTTPS)")
        instructions.append("   - After connecting, you'll have a graphical desktop session")
        if wine_prefix:
            instructions.append(f"   - Wine prefix location: {wine_prefix}")
        instructions.append("")
        instructions.append("2. Launch MT5 from the ThinLinc session:")
        instructions.append(f"   - Open a terminal in ThinLinc")
        instructions.append(f"   - Run: {wine_path} '{mt5_path}'")
        instructions.append("")
        instructions.append("3. Configure MT5 in the ThinLinc session:")
        instructions.append("   - Enter your MT5 credentials (login, password, server)")
        instructions.append("   - Enable autotrading if needed")
        instructions.append("   - Configure DLLs and webrequests as required")
        instructions.append("")
        if detection_result.x11_server.found:
            instructions.append("   Note: X11 server is available for GUI applications.")
        else:
            instructions.append("   Note: Ensure X11 server (Xvfb) is running for GUI access.")
    else:
        # Local environment instructions
        instructions.append("**Local Environment - Access MT5:**")
        instructions.append("")
        instructions.append("1. Launch MT5 using Wine:")
        instructions.append(f"   - Run: {wine_path} '{mt5_path}'")
        if wine_prefix:
            instructions.append(f"   - Wine prefix location: {wine_prefix}")
        instructions.append("")
        if detection_result.display_system == "wayland":
            instructions.append("   Note: You're using Wayland. GUI automation tools (xyphir/xdotool)")
            instructions.append("   are available if needed for automated configuration.")
        elif detection_result.display_system == "x11":
            instructions.append("   Note: You're using X11. GUI automation tools (xdotool)")
            instructions.append("   are available if needed for automated configuration.")
        instructions.append("")
        instructions.append("2. Configure MT5:")
        instructions.append("   - Enter your MT5 credentials (login, password, server)")
        instructions.append("   - Enable autotrading if needed")
        instructions.append("   - Configure DLLs and webrequests as required")
        instructions.append("")
        instructions.append("3. After configuration, return here and press Enter to continue setup.")

    return "\n".join(instructions)


def verify_mt5_configuration(detection_result: DetectionResult) -> VerificationResult:
    """
    Verify that MT5 configuration is accessible after pause.

    Args:
        detection_result: Current environment detection results

    Returns:
        VerificationResult with verification status
    """
    logger.debug("Verifying MT5 configuration accessibility")
    echo("[cyan]Verifying MT5 configuration...[/cyan]")

    # Check if MT5 executable is still accessible
    if not detection_result.mt5.found:
        logger.warning("MT5 not found in detection results")
        return VerificationResult(
            success=False,
            mt5_accessible=False,
            error="MT5 not found",
            recovery_suggestion="Ensure MT5 is installed and accessible",
        )

    if not detection_result.mt5.path:
        logger.warning("MT5 path not available")
        return VerificationResult(
            success=False,
            mt5_accessible=False,
            error="MT5 path not available",
            recovery_suggestion="Re-run environment detection to locate MT5",
        )

    # Check if Wine is still available (needed to run MT5) - check before MT5 path
    if not detection_result.wine.found or not detection_result.wine.path:
        logger.warning("Wine not found, MT5 cannot be launched")
        return VerificationResult(
            success=False,
            mt5_accessible=False,
            error="Wine not found",
            recovery_suggestion="Ensure Wine is installed and accessible",
        )

    # Check if Wine executable exists
    if not os.path.exists(detection_result.wine.path):
        logger.warning(f"Wine executable not found at: {detection_result.wine.path}")
        return VerificationResult(
            success=False,
            mt5_accessible=False,
            error=f"Wine executable not found at {detection_result.wine.path}",
            recovery_suggestion="Verify Wine installation path or reinstall Wine",
        )

    # Check if MT5 executable file exists
    if not os.path.exists(detection_result.mt5.path):
        logger.warning(f"MT5 executable not found at: {detection_result.mt5.path}")
        return VerificationResult(
            success=False,
            mt5_accessible=False,
            error=f"MT5 executable not found at {detection_result.mt5.path}",
            recovery_suggestion="Verify MT5 installation path or reinstall MT5",
        )

    logger.info("MT5 configuration verification successful")
    echo("[bold green]MT5 configuration verified[/bold green]")
    return VerificationResult(
        success=True,
        mt5_accessible=True,
    )


def pause_for_mt5_configuration(detection_result: DetectionResult) -> PauseResult:
    """
    Pause the installation process for MT5 manual configuration.

    Args:
        detection_result: Current environment detection results

    Returns:
        PauseResult with pause status and duration
    """
    logger.info("Initiating pause for MT5 configuration")
    pause_start = time.time()

    try:
        # Display pause message (AC #1 requires exact format)
        echo("\n" + "=" * 70)
        echo("⏸️  PAUSING FOR MT5 CONFIGURATION")
        echo("=" * 70)
        echo("")
        echo("Please configure MT5 (credentials, autotrading, DLLs, webrequests)")
        echo("")
        echo("Configuration checklist:")
        echo("  [bold green]MT5 credentials[/bold green] (login, password, server)")
        echo("  [bold green]Autotrading[/bold green] (enable if needed)")
        echo("  [bold green]DLLs[/bold green] (configure as required)")
        echo("  [bold green]Webrequests[/bold green] (configure as required)")
        echo("")
        echo("-" * 70)

        # Display MT5 GUI access instructions
        instructions = get_mt5_gui_instructions(detection_result)
        echo(instructions)

        echo("-" * 70)
        echo("")
        echo("After configuring MT5, return here and press Enter to continue setup.")
        echo("")

        # Wait for user input
        try:
            prompt("Press Enter to continue setup", default="", show_default=False)
            # User pressed Enter (or provided any input)
            pause_end = time.time()
            duration = pause_end - pause_start

            logger.info(f"Pause resumed by user after {duration:.1f} seconds")
            echo("\n▶️  Resuming setup...")
            echo("")

            return PauseResult(
                success=True,
                resumed=True,
                duration_seconds=duration,
            )
        except KeyboardInterrupt:
            # User pressed Ctrl+C
            pause_end = time.time()
            duration = pause_end - pause_start

            logger.warning(f"Pause cancelled by user (Ctrl+C) after {duration:.1f} seconds")
            echo("\n\n[yellow]Setup cancelled by user[/yellow]")
            echo("You can resume setup later by running: mt5linux setup")
            echo("")

            return PauseResult(
                success=False,
                resumed=False,
                duration_seconds=duration,
                error="User cancelled pause",
            )
        except EOFError:
            # Input stream closed (e.g., non-interactive terminal)
            pause_end = time.time()
            duration = pause_end - pause_start

            logger.warning(f"Pause interrupted (EOF) after {duration:.1f} seconds")
            echo("\n\n[yellow]Input stream closed - cannot wait for user input[/yellow]")
            echo("Setup will continue automatically...")
            echo("")

            return PauseResult(
                success=False,
                resumed=False,
                duration_seconds=duration,
                error="Input stream closed (non-interactive terminal)",
            )

    except Exception as e:
        # Unexpected error during pause
        pause_end = time.time()
        duration = pause_end - pause_start

        logger.error(f"Error during pause: {e}", exc_info=True)
        echo(f"\n\n[yellow]Error during pause:[/yellow] {e}")
        echo("Setup will continue automatically...")
        echo("")

        return PauseResult(
            success=False,
            resumed=False,
            duration_seconds=duration,
            error=str(e),
        )
