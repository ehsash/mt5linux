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
    from typer import echo
except ImportError:
    # Fallback if typer not available
    echo = print  # type: ignore

from mt5linux.detection import DetectionResult, detect_xyphir, detect_x11_server


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
        echo("   ⚠️  Sudo access required for installation")
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
                    echo(f"   ✅ xyphir installed via {pm_name}")
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
                    echo(f"   ✅ xyphir installed via {pm_name}")
                    return True
                else:
                    logger.warning(f"xyphir installation failed via {pm_name}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning(f"xyphir installation timed out via {pm_name}")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Error installing xyphir via {pm_name}: {e}")

    logger.warning("xyphir installation failed via all package managers")
    echo("   ⚠️  Could not install xyphir automatically")
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
    Configure xyphir for Wayland support.

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with configuration status
    """
    logger.info("Starting xyphir configuration")
    echo("🔧 Configuring xyphir for Wayland support...")

    # Check if xyphir is already detected
    if detection_result.xyphir.found and detection_result.xyphir.path:
        logger.info(f"xyphir already detected: {detection_result.xyphir.path}")
        echo(f"✅ xyphir already configured: {detection_result.xyphir.path}")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=True,
            fallback_to_x11=False,
            xyphir_path=detection_result.xyphir.path,
        )

    # Try to detect xyphir again (in case it was just installed)
    xyphir_info = detect_xyphir()
    if xyphir_info.found and xyphir_info.path:
        logger.info(f"xyphir detected: {xyphir_info.path}")
        echo(f"✅ xyphir found: {xyphir_info.path}")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=True,
            fallback_to_x11=False,
            xyphir_path=xyphir_info.path,
        )

    # xyphir not found - attempt to install it
    logger.info("xyphir not found - attempting installation")
    echo("⚠️  xyphir not found in PATH")
    if _attempt_install_xyphir():
        # Try to detect again after installation
        xyphir_info = detect_xyphir()
        if xyphir_info.found and xyphir_info.path:
            logger.info(f"xyphir detected after installation: {xyphir_info.path}")
            echo(f"✅ xyphir installed and configured: {xyphir_info.path}")
            return WaylandConfigResult(
                success=True,
                xyphir_configured=True,
                fallback_to_x11=False,
                xyphir_path=xyphir_info.path,
            )

    # Installation failed or xyphir still not found - provide instructions for manual installation
    logger.warning("xyphir not found - manual installation may be required")
    echo("   xyphir may require manual installation.")
    echo("   Please install xyphir for Wayland GUI automation support.")
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
    Verify that xyphir executable exists and can run.

    Note: This verifies the executable works, but does not test actual Wayland
    interaction (which would require a running Wayland session).

    Args:
        xyphir_path: Path to xyphir executable

    Returns:
        True if xyphir executable exists and can run, False otherwise
    """
    logger.debug(f"Verifying xyphir at {xyphir_path}")
    if not os.path.exists(xyphir_path):
        logger.warning(f"xyphir path does not exist: {xyphir_path}")
        return False

    if not os.access(xyphir_path, os.X_OK):
        logger.warning(f"xyphir path is not executable: {xyphir_path}")
        return False

    # Try to run xyphir with a help or version command to verify it works
    try:
        result = subprocess.run(
            [xyphir_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info(f"xyphir verification successful: {xyphir_path}")
            return True
        # Try alternative version flag
        result = subprocess.run(
            [xyphir_path, "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info(f"xyphir verification successful: {xyphir_path}")
            return True
        logger.warning(f"xyphir verification failed: return code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning("xyphir verification timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error verifying xyphir: {e}")

    return False


def fallback_to_x11(detection_result: DetectionResult) -> WaylandConfigResult:
    """
    Fall back to X11 when xyphir configuration fails.

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with X11 fallback status
    """
    logger.info("Attempting X11 fallback")
    echo("🔄 Falling back to X11 for GUI automation...")

    # Check if X11 server is available
    x11_info = detect_x11_server()
    if x11_info.found and x11_info.path:
        logger.info(f"X11 server detected: {x11_info.path}")
        echo(f"✅ X11 server available: {x11_info.path}")
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
        echo(f"✅ xdotool available for X11 GUI automation: {xdotool_path}")
        return WaylandConfigResult(
            success=True,
            xyphir_configured=False,
            fallback_to_x11=True,
            x11_server_path=xdotool_path,
        )

    logger.warning("X11 fallback not available - no X11 server or xdotool found")
    echo("⚠️  X11 fallback not available")
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
    Configure Wayland support (xyphir) with X11 fallback.

    This function orchestrates the Wayland configuration process:
    1. Attempts to configure xyphir
    2. Falls back to X11 if xyphir configuration fails
    3. Verifies the selected configuration

    Args:
        detection_result: Current environment detection results

    Returns:
        WaylandConfigResult with final configuration status
    """
    logger.info("Starting Wayland support configuration")
    echo("\n🖥️  Configuring Wayland support...")

    # Verify we're in the right environment
    if detection_result.environment_type != "local":
        logger.warning(f"Wayland configuration called in non-local environment: {detection_result.environment_type}")
        echo("⚠️  Wayland configuration only runs in local environment")
        return WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=False,
            error="Not a local environment",
            recovery_suggestion="Wayland configuration is only for local environments",
        )

    if detection_result.display_system != "wayland":
        logger.warning(f"Wayland configuration called in non-Wayland environment: {detection_result.display_system}")
        echo("⚠️  Wayland configuration only runs in Wayland display system")
        return WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=False,
            error="Not a Wayland display system",
            recovery_suggestion="Wayland configuration is only for Wayland display systems",
        )

    # Attempt to configure xyphir
    xyphir_result = configure_xyphir(detection_result)
    if xyphir_result.success and xyphir_result.xyphir_configured:
        # Verify xyphir if path is available
        if xyphir_result.xyphir_path and verify_xyphir(xyphir_result.xyphir_path):
            logger.info("Wayland support configured successfully with xyphir")
            echo("✅ Wayland support configured with xyphir")
            return xyphir_result
        else:
            logger.warning("xyphir configuration succeeded but verification failed")
            echo("⚠️  xyphir found but verification failed, falling back to X11...")
            # Fall through to X11 fallback

    # Fall back to X11 if xyphir configuration failed
    logger.info("xyphir configuration failed, attempting X11 fallback")
    x11_result = fallback_to_x11(detection_result)
    if x11_result.success:
        logger.info("X11 fallback successful")
        echo("✅ Falling back to X11 for GUI automation")
        return x11_result

    # Both xyphir and X11 fallback failed
    logger.error("Both xyphir configuration and X11 fallback failed")
    echo("❌ Wayland support configuration failed")
    echo("   Neither xyphir nor X11 fallback is available")
    echo("   GUI automation may not work properly")

    return WaylandConfigResult(
        success=False,
        xyphir_configured=False,
        fallback_to_x11=False,
        error="Both xyphir and X11 fallback failed",
        recovery_suggestion="Install xyphir or X11 server (Xvfb) and xdotool for GUI automation",
    )
