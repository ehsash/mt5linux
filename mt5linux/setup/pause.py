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

import subprocess
import shutil

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

    # Get MT5 path, Wine path, and Wine prefix
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
    
    # Also try to get Wine prefix from config if available
    if not wine_prefix:
        try:
            from mt5linux.config import get_config
            config = get_config()
            if config and config.wine and config.wine.prefix_path:
                wine_prefix = config.wine.prefix_path
        except Exception:
            pass  # Config not available, use defaults

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
        instructions.append("**Local Environment - MT5 will be launched automatically:**")
        instructions.append("")
        if wine_prefix:
            instructions.append(f"   - Wine prefix: {wine_prefix}")
        if detection_result.display_system == "wayland":
            instructions.append("   - MT5 will be launched automatically (Wine uses XWayland on Wayland)")
        instructions.append("")
        instructions.append("1. Configure MT5 in the window that will open:")
        instructions.append("   - Enter your MT5 credentials (login, password, server)")
        instructions.append("   - Enable autotrading if needed")
        instructions.append("   - Configure DLLs and webrequests as required")
        instructions.append("")
        instructions.append("2. After configuration, return here and press Enter to continue setup.")

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
        
        # Automatically launch MT5 for the user
        logger.info(f"MT5 detection status: found={detection_result.mt5.found}, path={detection_result.mt5.path}")
        if detection_result.mt5.found and detection_result.mt5.path:
            if not os.path.exists(detection_result.mt5.path):
                logger.error(f"MT5 path does not exist: {detection_result.mt5.path}")
                echo(f"[bold red]Error: MT5 path does not exist: {detection_result.mt5.path}[/bold red]")
                echo("Please launch MT5 manually using the instructions above.")
            else:
                echo("[cyan]Launching MT5 terminal...[/cyan]")
                logger.info(f"Launching MT5 terminal from: {detection_result.mt5.path}")
            
            # Get Wine path and prefix
            wine_path = detection_result.wine.path if detection_result.wine.found else shutil.which("wine")
            if not wine_path:
                logger.error("Wine not found, cannot launch MT5")
                echo("[bold red]Error: Wine not found, cannot launch MT5[/bold red]")
                echo("Please launch MT5 manually using the instructions above.")
            else:
                # Extract Wine prefix
                wine_prefix = None
                mt5_dir = os.path.dirname(detection_result.mt5.path)
                if "drive_c" in mt5_dir:
                    prefix_candidate = os.path.dirname(mt5_dir)
                    if os.path.isdir(prefix_candidate):
                        wine_prefix = prefix_candidate
                
                # Try to get from config
                if not wine_prefix:
                    try:
                        from mt5linux.config import get_config
                        config = get_config()
                        if config and config.wine and config.wine.prefix_path:
                            wine_prefix = config.wine.prefix_path
                    except Exception:
                        pass
                
                # Fallback to default
                if not wine_prefix:
                    wine_prefix = os.path.join(os.getcwd(), ".mt5")
                
                # Set up environment
                env = os.environ.copy()
                env["WINEPREFIX"] = wine_prefix
                env["WINEDEBUG"] = "-all"
                
                # Launch MT5
                # On Wayland, use Wine virtual desktop for proper mouse/keyboard input
                # The explorer /desktop= option creates a contained window that handles input correctly
                try:
                    if detection_result.display_system == "wayland":
                        # Use virtual desktop on Wayland for proper input handling
                        # This creates a Wine-managed window that captures mouse/keyboard correctly
                        cmd = [
                            wine_path,
                            "explorer",
                            "/desktop=MT5,1920x1080",
                            detection_result.mt5.path
                        ]
                        logger.info("Wayland detected - using Wine virtual desktop for input compatibility")
                        echo("[cyan]Using Wine virtual desktop for Wayland input compatibility[/cyan]")
                    else:
                        cmd = [wine_path, detection_result.mt5.path]
                    logger.info(f"Launching MT5 with Wine: {' '.join(cmd)}")
                    logger.info(f"Environment: WINEPREFIX={wine_prefix}, DISPLAY={env.get('DISPLAY', 'not set')}")
                    if detection_result.display_system == "wayland":
                        echo(f"[dim]Launching MT5 in virtual desktop: {' '.join(cmd)}[/dim]")
                    else:
                        echo(f"[dim]Launching: {' '.join(cmd)}[/dim]")
                    
                    # Launch in background so user can continue
                    # Don't suppress stderr initially so we can see any errors
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    
                    # Give it a moment to start and check if it's still running
                    time.sleep(1)
                    if process.poll() is None:
                        # Process is still running, good
                        echo("[bold green]MT5 terminal launched![/bold green]")
                        echo("")
                        logger.info("MT5 process started successfully")
                    else:
                        # Process exited immediately, something went wrong
                        stdout, stderr = process.communicate(timeout=2)
                        error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                        logger.error(f"MT5 process exited immediately with code {process.returncode}")
                        logger.error(f"MT5 stderr: {error_msg[:500]}")
                        echo(f"[bold red]MT5 failed to start (exit code: {process.returncode})[/bold red]")
                        if error_msg:
                            echo(f"[yellow]Error: {error_msg[:200]}[/yellow]")
                        echo("Please launch MT5 manually using the instructions above.")
                except Exception as e:
                    logger.error(f"Failed to launch MT5: {e}", exc_info=True)
                    echo(f"[bold red]Failed to launch MT5: {e}[/bold red]")
                    echo("Please launch MT5 manually using the instructions above.")
        else:
            echo("[yellow]MT5 path not available - please launch MT5 manually[/yellow]")
        
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
