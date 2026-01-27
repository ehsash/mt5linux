"""Wayland configuration module for mt5linux setup automation."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

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

from mt5linux.detection import DetectionResult, detect_ydotool, detect_x11_server


def _check_sudo_access() -> bool:
    """
    Check if the current user has sudo access.

    Returns:
        True if user has sudo access, False otherwise
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _attempt_install_xyphir() -> bool:
    """
    Attempt to install xyphir via system package manager.

    Returns:
        True if installation succeeded, False otherwise
    """
    logger.info("Attempting to install xyphir via package manager")
    echo("   Attempting to install xyphir...")

    # Check for sudo access
    if not _check_sudo_access():
        logger.warning("No sudo access available for xyphir installation")
        echo("   [yellow]Sudo access required for installation[/yellow]")
        return False

    # Try common package managers
    package_managers = [
        ("apt", ["sudo", "apt-get", "update", "-qq", "&&", "sudo", "apt-get", "install", "-y", "xyphir"]),
        ("dnf", ["sudo", "dnf", "install", "-y", "xyphir"]),
        ("yum", ["sudo", "yum", "install", "-y", "xyphir"]),
        ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "xyphir"]),
        ("zypper", ["sudo", "zypper", "install", "-y", "xyphir"]),
    ]

    for pm_name, cmd_parts in package_managers:
        pm_path = shutil.which(pm_name.split()[0] if " " in pm_name else pm_name)
        if not pm_path:
            continue

        logger.info(f"Attempting xyphir installation via {pm_name}")
        try:
            # For apt-get, we need to handle the && separately
            if pm_name == "apt":
                # First update
                update_result = subprocess.run(
                    ["sudo", "apt-get", "update", "-qq"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if update_result.returncode != 0:
                    logger.warning(f"apt-get update failed: {update_result.stderr}")
                    continue

                # Then install
                install_result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "xyphir"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if install_result.returncode == 0:
                    logger.info(f"xyphir installed successfully via {pm_name}")
                    echo(f"   [bold green]xyphir installed via {pm_name}[/bold green]")
                    return True
                else:
                    logger.warning(f"xyphir installation failed via {pm_name}: {install_result.stderr}")
            else:
                # For other package managers, single command
                result = subprocess.run(
                    cmd_parts[1:],  # Skip 'sudo' from cmd_parts, add it separately
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"xyphir installed successfully via {pm_name}")
                    echo(f"   [bold green]xyphir installed via {pm_name}[/bold green]")
                    return True
                else:
                    logger.warning(f"xyphir installation failed via {pm_name}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning(f"xyphir installation timed out via {pm_name}")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Error installing xyphir via {pm_name}: {e}")

    logger.warning("xyphir installation failed via all package managers")
    echo("   [yellow]Could not install xyphir automatically[/yellow]")
    return False


@dataclass
class WaylandConfigResult:
    """Result of Wayland configuration operation."""

    success: bool
    xyphir_configured: bool
    fallback_to_x11: bool
    xyphir_path: Optional[str] = None
    x11_server_path: Optional[str] = None
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


def configure_xyphir(detection_result: DetectionResult) -> WaylandConfigResult:
    """
    Configure ydotool for Wayland automation (optional).
    
    Note: Wine uses XWayland automatically on Wayland, so ydotool is only needed
    for GUI automation, not for basic Wine functionality.

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with configuration status
    """
    logger.info("Starting ydotool configuration (optional for automation)")
    echo("🔧 Configuring Wayland automation support (ydotool, optional)...")

    # Check if ydotool is already detected (optional for automation)
    # Note: Wine uses XWayland automatically on Wayland, so ydotool is only for automation
    if detection_result.ydotool.found and detection_result.ydotool.path:
        logger.info(f"ydotool already detected: {detection_result.ydotool.path}")
        echo(f"[bold green]ydotool already available:[/bold green] {detection_result.ydotool.path} (for automation)")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=True,  # Keep for compatibility, but means ydotool is available
            fallback_to_x11=False,
            xyphir_path=detection_result.ydotool.path,  # Keep field name for compatibility
        )

    # Try to detect ydotool again (in case it was just installed)
    ydotool_info = detect_ydotool()
    if ydotool_info.found and ydotool_info.path:
        logger.info(f"ydotool detected: {ydotool_info.path}")
        echo(f"[bold green]ydotool found:[/bold green] {ydotool_info.path} (for automation)")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=True,  # Keep for compatibility
            fallback_to_x11=False,
            xyphir_path=ydotool_info.path,  # Keep field name for compatibility
        )

    # ydotool not found - this is OK, Wine works through XWayland automatically
    # ydotool is only needed for automation, not for basic Wine functionality
    logger.info("ydotool not found - Wine will still work through XWayland")
    echo("[dim]ydotool not found (optional for automation only)[/dim]")
    echo("   Wine uses XWayland automatically on Wayland - input will work without ydotool")
    echo("   Falling back to X11 for GUI automation...")

    return WaylandConfigResult(
        success=False,
        xyphir_configured=False,
        fallback_to_x11=True,
        error="xyphir not found",
        recovery_suggestion="Install xyphir manually or use X11 fallback",
    )


def verify_xyphir(xyphir_path: str) -> bool:
    """
    Verify that ydotool executable exists and can run.

    Note: This verifies the executable works, but does not test actual Wayland
    interaction (which would require a running Wayland session and ydotoold daemon).

    Args:
        xyphir_path: Path to ydotool executable (kept parameter name for compatibility)

    Returns:
        True if ydotool executable exists and can run, False otherwise
    """
    logger.debug(f"Verifying ydotool at {xyphir_path}")
    if not os.path.exists(xyphir_path):
        logger.warning(f"ydotool path does not exist: {xyphir_path}")
        return False

    if not os.access(xyphir_path, os.X_OK):
        logger.warning(f"ydotool path is not executable: {xyphir_path}")
        return False

    # Try to run ydotool with a help or version command to verify it works
    try:
        result = subprocess.run(
            [xyphir_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info(f"ydotool verification successful: {xyphir_path}")
            return True
        # Try alternative version flag
        result = subprocess.run(
            [xyphir_path, "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info(f"ydotool verification successful: {xyphir_path}")
            return True
        logger.warning(f"ydotool verification failed: return code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning("ydotool verification timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error verifying ydotool: {e}")

    return False


def fallback_to_x11(detection_result: DetectionResult) -> WaylandConfigResult:
    """
    Fall back to X11 when ydotool configuration fails or is not available.

    Note: This is only for GUI automation. Wine uses XWayland automatically
    on Wayland for basic functionality.

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with X11 fallback status
    """
    logger.info("Attempting X11 fallback for GUI automation")
    echo("🔄 Falling back to X11 for GUI automation...")

    # Check if X11 server is available
    x11_info = detect_x11_server()
    if x11_info.found and x11_info.path:
        logger.info(f"X11 server detected: {x11_info.path}")
        echo(f"[bold green]X11 server available:[/bold green] {x11_info.path}")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=False,
            fallback_to_x11=True,
            x11_server_path=x11_info.path,
        )

    # Check for xdotool (X11 GUI automation tool)
    xdotool_path = shutil.which("xdotool")
    if xdotool_path:
        logger.info(f"xdotool detected: {xdotool_path}")
        echo(f"[bold green]xdotool available for X11 GUI automation:[/bold green] {xdotool_path}")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=False,
            fallback_to_x11=True,
            x11_server_path=xdotool_path,
        )

    logger.warning("X11 fallback not available - no X11 server or xdotool found")
    echo("[yellow]X11 fallback not available[/yellow]")
    echo("   Neither X11 server nor xdotool found.")
    echo("   GUI automation may not work properly.")

    return WaylandConfigResult(
        success=False,
        xyphir_configured=False,
        fallback_to_x11=False,
        error="X11 fallback not available",
        recovery_suggestion="Install X11 server (Xvfb) or xdotool for GUI automation",
    )


def configure_wayland_support(detection_result: DetectionResult) -> WaylandConfigResult:
    """
    Configure Wayland automation support (ydotool) with X11 fallback.

    Note: Wine uses XWayland automatically on Wayland, so this function only
    configures optional automation tools (ydotool). Basic Wine functionality
    works without any additional configuration.

    This function orchestrates the Wayland automation configuration process:
    1. Attempts to configure ydotool (optional, for automation)
    2. Falls back to X11 if ydotool configuration fails
    3. Verifies the selected configuration

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with final configuration status
    """
    logger.info("Starting Wayland automation support configuration")
    echo("\n[cyan]Configuring Wayland automation support...[/cyan]")

    # Verify we're in the right environment
    if detection_result.environment_type != "local":
        logger.warning(f"Wayland configuration called in non-local environment: {detection_result.environment_type}")
        echo("[yellow]Wayland configuration only runs in local environment[/yellow]")
        return WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=False,
            error="Not a local environment",
            recovery_suggestion="Wayland configuration is only for local environments",
        )

    if detection_result.display_system != "wayland":
        logger.warning(f"Wayland configuration called in non-Wayland environment: {detection_result.display_system}")
        echo("[yellow]Wayland configuration only runs in Wayland display system[/yellow]")
        return WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=False,
            error="Not a Wayland display system",
            recovery_suggestion="Wayland configuration is only for Wayland display systems",
        )

    # Attempt to configure ydotool (optional for automation)
    ydotool_result = configure_xyphir(detection_result)  # Function name kept for compatibility
    if ydotool_result.success and ydotool_result.xyphir_configured:
        # Verify ydotool if path is available
        if ydotool_result.xyphir_path and verify_xyphir(ydotool_result.xyphir_path):
            logger.info("Wayland automation support configured successfully with ydotool")
            echo("[bold green]Wayland automation support configured (ydotool available)[/bold green]")
            return ydotool_result
        else:
            logger.warning("ydotool configuration succeeded but verification failed")
            echo("[yellow]ydotool found but verification failed, falling back to X11...[/yellow]")
            # Fall through to X11 fallback

    # Fall back to X11 if ydotool configuration failed (or not needed)
    # Note: Wine still works through XWayland even without ydotool
    logger.info("ydotool not configured, attempting X11 fallback for automation")
    x11_result = fallback_to_x11(detection_result)
    if x11_result.success:
        logger.info("X11 fallback successful for automation")
        echo("[bold green]Falling back to X11 for GUI automation[/bold green]")
        echo("[dim]Note: Wine still works through XWayland for basic functionality[/dim]")
        return x11_result

    # Both ydotool and X11 fallback failed (but Wine still works through XWayland)
    logger.warning("Both ydotool and X11 fallback failed, but Wine will still work through XWayland")
    echo("[yellow]Wayland automation configuration incomplete[/yellow]")
    echo("   Neither ydotool nor X11 fallback is available for automation")
    echo("   [dim]Note: Wine will still work through XWayland for basic functionality[/dim]")
    echo("   GUI automation may not work properly")

    return WaylandConfigResult(
        success=False,
        xyphir_configured=False,
        fallback_to_x11=False,
        error="Both ydotool and X11 fallback failed",
        recovery_suggestion="Install ydotool or X11 server (Xvfb) and xdotool for GUI automation (optional)",
    )
